import argparse
import json
import os
import sys
from datetime import datetime
from collections import defaultdict
import random

import numpy as np
from sklearn.decomposition import TruncatedSVD
import torch
import torch.nn as nn
import torch.optim as optim

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.spotify_dnn import SpotifySimilarityDNN

def parse_and_sort(folder: str):
    all_records = []
    for fname in sorted(os.listdir(folder)):
        if fname.startswith("Streaming_History_Audio_") and fname.endswith(".json"):
            fpath = os.path.join(folder, fname)
            with open(fpath, encoding="utf-8") as f:
                records = json.load(f)
            all_records.extend(records)
        elif fname == "RawCoreStream.json":
            fpath = os.path.join(folder, fname)
            with open(fpath, encoding="utf-8") as f:
                records = json.load(f)
            for r in records:
                if r.get("message_content_uri") and r.get("message_content_uri").startswith("spotify:track:"):
                    r["spotify_track_uri"] = r["message_content_uri"]
                    r["master_metadata_track_name"] = "Track " + r["message_content_uri"].split(":")[-1]
                    r["master_metadata_album_artist_name"] = "Unknown Artist"
                    ts_str = r.get("timestamp_utc")
                    if ts_str and "." in ts_str:
                        ts_str = ts_str.split(".")[0] + "Z"
                    r["ts"] = ts_str
                    all_records.append(r)
    
    # Filter valid tracks
    filtered = [
        r for r in all_records
        if r.get("spotify_track_uri") and r.get("master_metadata_track_name")
    ]
    
    # Sort by timestamp
    for r in filtered:
        try:
            r["parsed_ts"] = datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            r["parsed_ts"] = datetime.min
        
    filtered.sort(key=lambda x: x["parsed_ts"])
    return filtered

def extract_sessions(records, gap_minutes=30):
    sessions = []
    current_session = []
    
    for i, r in enumerate(records):
        if not current_session:
            current_session.append(r)
            continue
            
        prev_r = current_session[-1]
        diff = (r["parsed_ts"] - prev_r["parsed_ts"]).total_seconds() / 60.0
        
        if diff <= gap_minutes:
            current_session.append(r)
        else:
            if len(current_session) > 1:
                sessions.append(current_session)
            current_session = [r]
            
    if len(current_session) > 1:
        sessions.append(current_session)
        
    return sessions

def build_cooccurrence(sessions):
    track_counts = defaultdict(int)
    for s in sessions:
        for r in s:
            track_counts[r["spotify_track_uri"]] += 1
            
    # Map URI to index
    # Only keep tracks played at least a few times to reduce noise
    valid_tracks = [uri for uri, count in track_counts.items() if count >= 2]
    uri_to_idx = {uri: i for i, uri in enumerate(valid_tracks)}
    idx_to_info = {}
    for s in sessions:
        for r in s:
            uri = r["spotify_track_uri"]
            if uri in uri_to_idx and uri_to_idx[uri] not in idx_to_info:
                idx_to_info[uri_to_idx[uri]] = {
                    "uri": uri,
                    "name": r["master_metadata_track_name"],
                    "artist": r["master_metadata_album_artist_name"]
                }
                
    N = len(valid_tracks)
    print(f"Total unique valid tracks (>=2 plays): {N}")
    
    import scipy.sparse as sp
    cooc = sp.lil_matrix((N, N), dtype=np.float32)
    
    window = 5 # track context window
    for s in sessions:
        uris = [r["spotify_track_uri"] for r in s]
        for i, u1 in enumerate(uris):
            if u1 not in uri_to_idx: continue
            idx1 = uri_to_idx[u1]
            
            start = max(0, i - window)
            end = min(len(uris), i + window + 1)
            for j in range(start, end):
                if i == j: continue
                u2 = uris[j]
                if u2 not in uri_to_idx: continue
                idx2 = uri_to_idx[u2]
                cooc[idx1, idx2] += 1.0
                
    return cooc.tocsr(), uri_to_idx, idx_to_info

def generate_training_data(sessions, uri_to_idx, track_embeddings, num_samples=10000):
    pos_pairs = []
    neg_pairs = []
    
    # Pre-flatten sessions for negative sampling
    all_valid_uris = list(uri_to_idx.keys())
    
    print("Generating positive pairs...")
    for s in sessions:
        uris = [r["spotify_track_uri"] for r in s if r["spotify_track_uri"] in uri_to_idx]
        if len(uris) < 2: continue
        for i in range(len(uris)-1):
            if random.random() < 0.1: # sample 10% of adjacent pairs to prevent explosion
                pos_pairs.append((uris[i], uris[i+1]))
                if len(pos_pairs) >= num_samples // 2:
                    break
        if len(pos_pairs) >= num_samples // 2:
            break
            
    print("Generating negative pairs...")
    while len(neg_pairs) < len(pos_pairs):
        u1 = random.choice(all_valid_uris)
        u2 = random.choice(all_valid_uris)
        if u1 != u2:
            neg_pairs.append((u1, u2))
            
    X_seed = []
    X_cand = []
    y = []
    
    for u1, u2 in pos_pairs:
        X_seed.append(track_embeddings[uri_to_idx[u1]])
        X_cand.append(track_embeddings[uri_to_idx[u2]])
        y.append([1.0])
        
    for u1, u2 in neg_pairs:
        X_seed.append(track_embeddings[uri_to_idx[u1]])
        X_cand.append(track_embeddings[uri_to_idx[u2]])
        y.append([0.0])
        
    # Shuffle
    idx = list(range(len(y)))
    random.shuffle(idx)
    
    X_seed = torch.tensor(np.array(X_seed)[idx], dtype=torch.float32)
    X_cand = torch.tensor(np.array(X_cand)[idx], dtype=torch.float32)
    y = torch.tensor(np.array(y)[idx], dtype=torch.float32)
    
    return X_seed, X_cand, y

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--embed-dim", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()
    
    print("Parsing JSON...")
    records = parse_and_sort(args.folder)
    print(f"Total valid play events: {len(records)}")
    
    sessions = extract_sessions(records)
    print(f"Total sessions: {len(sessions)}")
    
    print("Building co-occurrence matrix...")
    cooc, uri_to_idx, idx_to_info = build_cooccurrence(sessions)
    
    print("Running SVD...")
    svd = TruncatedSVD(n_components=args.embed_dim, random_state=42)
    embeddings = svd.fit_transform(cooc) # (N, embed_dim)
    
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    embeddings = embeddings / norms
    
    print("Generating training data...")
    X_seed, X_cand, y = generate_training_data(sessions, uri_to_idx, embeddings, num_samples=20000)
    
    print(f"Training DNN on {len(y)} pairs (input_dim={args.embed_dim * 2})...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    model = SpotifySimilarityDNN(input_dim=args.embed_dim * 2, hidden_dim=64).to(device)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    
    X_seed, X_cand, y = X_seed.to(device), X_cand.to(device), y.to(device)
    
    for epoch in range(args.epochs):
        optimizer.zero_grad()
        outputs = model(X_seed, X_cand)
        loss = criterion(outputs, y)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 5 == 0:
            with torch.no_grad():
                preds = (outputs >= 0.5).float()
                acc = (preds == y).float().mean().item()
            print(f"Epoch {epoch+1:2d}/{args.epochs} | Loss: {loss.item():.4f} | Acc: {acc:.3f}")
            
    os.makedirs("data/models", exist_ok=True)
    torch.save(model.state_dict(), "data/models/spotify_model.pth")
    
    # Save embeddings mapping
    track_embeddings_dict = {}
    for uri, idx in uri_to_idx.items():
        track_embeddings_dict[uri] = {
            "embedding": embeddings[idx].tolist(),
            "name": idx_to_info[idx]["name"],
            "artist": idx_to_info[idx]["artist"]
        }
        
    with open("data/models/track_embeddings.json", "w", encoding="utf-8") as f:
        json.dump({"embed_dim": args.embed_dim, "tracks": track_embeddings_dict}, f)
        
    print("Saved spotify_model.pth and track_embeddings.json")
    print("DONE.")

if __name__ == "__main__":
    main()
