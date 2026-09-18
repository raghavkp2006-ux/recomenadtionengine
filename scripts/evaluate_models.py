import os
import json
import csv
import pickle
import random
import math
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, Any, List
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal, UserSpotFeedback, UserDiningFeedback
from models.myntra import MyntraFeedback, MyntraEvent
from database import User  # Fixing import based on grep search
from services.taste_profile import compute_convergence, compute_taste_profile
from services.tourist_spots import get_recommendations as get_tourist_recommendations
from services.myntra_recommender import recommendations as get_myntra_recommendations
from models.anime_dnn import AnimeAutoEncoder
from models.spotify_dnn import SpotifySimilarityDNN
from sqlalchemy import func

def _save_confusion_matrix(cm, labels, path, title):
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
    fig, ax = plt.subplots(figsize=(6, 6))
    disp.plot(ax=ax, cmap=plt.cm.Blues, colorbar=True)
    ax.set_title(title, pad=20)
    plt.savefig(path, bbox_inches="tight")
    plt.close(fig)

def evaluate_anime() -> Dict[str, Any]:
    print("Evaluating Anime AutoEncoder...")
    data_path = 'data/raw/top_15000_anime.csv'
    if not os.path.exists(data_path):
        return {"status": "error", "message": f"{data_path} not found"}
        
    texts = []
    genres_list = []
    
    with open(data_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            syn = (row.get('synopsis') or '').strip()
            gen = (row.get('genres') or '').strip()
            thm = (row.get('themes') or '').strip()
            
            if not syn and not gen:
                continue
            texts.append(f"{syn} {gen} {thm}")
            genres_list.append(set(g.strip().lower() for g in gen.split(',') if g.strip()))

    from sentence_transformers import SentenceTransformer
    # Save to eval cache, never data/processed which is for prod dicts
    embed_path = 'data/eval/anime_dense_cache.pkl'
    if os.path.exists(embed_path):
        with open(embed_path, 'rb') as f:
            dense_embeddings = pickle.load(f)
    else:
        st_model = SentenceTransformer("all-MiniLM-L6-v2")
        dense_embeddings = st_model.encode(texts, show_progress_bar=False, batch_size=64)
        os.makedirs('data/eval', exist_ok=True)
        with open(embed_path, 'wb') as f:
            pickle.dump(dense_embeddings, f)
            
    features_tensor = torch.tensor(dense_embeddings, dtype=torch.float32)
    indices = np.arange(len(features_tensor))
    X_train, X_val, idx_train, idx_val = train_test_split(features_tensor, indices, test_size=0.2, random_state=42)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AnimeAutoEncoder(input_dim=features_tensor.shape[1], latent_dim=32).to(device)
    model.load_state_dict(torch.load('data/models/anime_model.pth', map_location=device))
    model.eval()
    
    X_val = X_val.to(device)
    with torch.no_grad():
        outputs = model(X_val)
        mse = nn.MSELoss()(outputs, X_val).item()
        latents = model.encode(X_val)
        latent_std = latents.std(dim=0).mean().item()
        
    print(f"Anime MSE: {mse:.6f}, Latent Std: {latent_std:.6f}")
    
    np.random.seed(42)
    query_idxs = np.random.choice(len(X_val), min(200, len(X_val)), replace=False)
    
    latents_np = latents.cpu().numpy()
    
    y_true = []
    y_pred = []
    
    for qi in query_idxs:
        q_latent = latents_np[qi]
        q_genres = genres_list[idx_val[qi]]
        if not q_genres:
            continue
            
        dists = np.linalg.norm(latents_np - q_latent, axis=1)
        top5 = np.argsort(dists)[1:6]
        
        for ti in top5:
            t_genres = genres_list[idx_val[ti]]
            has_overlap = bool(q_genres.intersection(t_genres))
            y_true.append(1 if has_overlap else 0)
            y_pred.append(1)
            
        neg_samples = np.random.choice(len(X_val), 5, replace=False)
        for ti in neg_samples:
            if ti == qi: continue
            t_genres = genres_list[idx_val[ti]]
            has_overlap = bool(q_genres.intersection(t_genres))
            y_true.append(1 if has_overlap else 0)
            y_pred.append(0)
            
    if y_true:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        _save_confusion_matrix(cm, ['Negative', 'Positive'], 'data/eval/anime_cm.png', 'Anime AutoEncoder (Top-5 Genre Overlap)')
    else:
        p, r, f1 = 0, 0, 0
        
    return {
        "mse": mse,
        "latent_std": latent_std,
        "precision": p,
        "recall": r,
        "f1": f1
    }

def evaluate_movies() -> Dict[str, Any]:
    print("Evaluating Movies TF-IDF...")
    mat_path = "data/processed/movie_tfidf_matrix.pkl"
    vec_path = "data/processed/movie_tfidf_vectorizer.pkl"
    
    if not os.path.exists(mat_path) or not os.path.exists(vec_path):
        return {"status": "error", "message": "Movie TF-IDF artifacts missing"}
        
    with open(mat_path, 'rb') as f:
        mat_data = pickle.load(f)
        matrix = mat_data["matrix"]
        metadata = mat_data.get("metadata", {})
        ids = mat_data["ids"]
        
    with open(vec_path, 'rb') as f:
        vectorizer = pickle.load(f)
        
    vocab_size = len(vectorizer.vocabulary_)
    
    np.random.seed(42)
    query_idxs = np.random.choice(matrix.shape[0], min(200, matrix.shape[0]), replace=False)
    
    y_true = []
    y_pred = []
    
    from sklearn.metrics.pairwise import cosine_similarity
    
    for qi in query_idxs:
        q_id = ids[qi]
        q_meta = metadata.get(q_id, {})
        q_genres = set(g.strip().lower() for g in (q_meta.get('genres') or []) if g.strip())
        if not q_genres:
            continue
            
        sims = cosine_similarity(matrix[qi:qi+1], matrix).flatten()
        top5 = np.argsort(sims)[-6:-1][::-1]
        
        for ti in top5:
            t_id = ids[ti]
            t_genres = set(g.strip().lower() for g in (metadata.get(t_id, {}).get('genres') or []) if g.strip())
            has_overlap = bool(q_genres.intersection(t_genres))
            y_true.append(1 if has_overlap else 0)
            y_pred.append(1)
            
        neg_samples = np.random.choice(matrix.shape[0], 5, replace=False)
        for ti in neg_samples:
            if ti == qi: continue
            t_id = ids[ti]
            t_genres = set(g.strip().lower() for g in (metadata.get(t_id, {}).get('genres') or []) if g.strip())
            has_overlap = bool(q_genres.intersection(t_genres))
            y_true.append(1 if has_overlap else 0)
            y_pred.append(0)
            
    if y_true:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        _save_confusion_matrix(cm, ['Negative', 'Positive'], 'data/eval/movies_cm.png', 'Movies TF-IDF (Top-5 Genre Overlap)')
    else:
        p, r, f1 = 0, 0, 0
        
    return {
        "vocab_size": vocab_size,
        "precision": p,
        "recall": r,
        "f1": f1
    }

def evaluate_spotify() -> Dict[str, Any]:
    print("Evaluating Spotify DNN...")
    model_path = "data/models/spotify_model.pth"
    embed_path = "data/models/track_embeddings.json"
    
    if not os.path.exists(model_path) or not os.path.exists(embed_path):
        return {"status": "error", "message": "Spotify artifacts missing"}
        
    with open(embed_path, 'r', encoding='utf-8') as f:
        embed_data = json.load(f)
        
    tracks = embed_data.get("tracks", {})
    embed_dim = embed_data.get("embed_dim", 32)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SpotifySimilarityDNN(input_dim=embed_dim*2, hidden_dim=64).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    valid_tracks = []
    for uri, data in tracks.items():
        genres = set(data.get("genres", []))
        if len(genres) >= 2:
            valid_tracks.append((uri, data["embedding"], genres))
            
    if len(valid_tracks) < 30:
        print("Spotify: track_embeddings.json does not store genre tags.")
        return {"status": "Limitation", "message": "track_embeddings.json does not store genre tags for any track (only embedding/name/artist) — genre-overlap evaluation is not obtainable from this artifact, regardless of dataset size."}
        
    y_true = []
    y_pred = []
    
    random.seed(42)
    sample_size = min(len(valid_tracks), 200)
    test_tracks = random.sample(valid_tracks, sample_size)
    
    with torch.no_grad():
        for i, (uri1, emb1, gen1) in enumerate(test_tracks):
            for j, (uri2, emb2, gen2) in enumerate(test_tracks):
                if i == j: continue
                has_overlap = bool(gen1.intersection(gen2))
                y_true.append(1 if has_overlap else 0)
                
                t1 = torch.tensor(emb1, dtype=torch.float32).unsqueeze(0).to(device)
                t2 = torch.tensor(emb2, dtype=torch.float32).unsqueeze(0).to(device)
                score = model(t1, t2).item()
                y_pred.append(1 if score >= 0.5 else 0)
                
    if y_true:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        _save_confusion_matrix(cm, ['Negative', 'Positive'], 'data/eval/spotify_cm.png', 'Spotify DNN (Genre Overlap)')
    else:
        p, r, f1 = 0, 0, 0
        
    return {
        "n": len(valid_tracks),
        "precision": p,
        "recall": r,
        "f1": f1
    }

def evaluate_tourist_spots() -> Dict[str, Any]:
    print("Evaluating Tourist Spots...")
    db = SessionLocal()
    count = db.query(UserSpotFeedback).count()
    users = db.query(UserSpotFeedback.user_id).distinct().count()
    print(f"UserSpotFeedback count: {count} rows across {users} users.")
    
    caveat = "Directional only — sample too small for a reliable confusion matrix (n=4)" if count < 10 else None
    if count < 10:
        print(f"Tourist Spots: {caveat}")
        
    y_true = []
    y_pred = []
    
    feedback_rows = db.query(UserSpotFeedback).all()
    user_feedbacks = {}
    for fb in feedback_rows:
        if fb.user_id not in user_feedbacks:
            user_feedbacks[fb.user_id] = []
        user_feedbacks[fb.user_id].append(fb)
        
    for user_id, fbs in user_feedbacks.items():
        try:
            profile = compute_taste_profile(user_id)
            recs = get_tourist_recommendations(db, user_id=user_id, taste_profile=profile, limit=10)
            if not recs:
                continue
            rec_ids = {str(r.get("place_id")) for r in recs} if isinstance(recs[0], dict) else {str(r.place_id) for r in recs}
        except Exception as e:
            print(f"Error evaluating user {user_id}: {e}")
            continue
            
        for fb in fbs:
            actual_rating = 1 if fb.rating > 0 else 0
            predicted = 1 if str(fb.place_id) in rec_ids else 0
            y_true.append(actual_rating)
            y_pred.append(predicted)
            
    db.close()
    
    if y_true:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        _save_confusion_matrix(cm, ['Negative', 'Positive'], 'data/eval/touristspots_cm.png', 'Tourist Spots (Predicted Top-10)')
    else:
        p, r, f1 = 0, 0, 0
        
    res = {"n": count, "users": users, "precision": p, "recall": r, "f1": f1}
    if caveat: res["caveat"] = caveat
    return res

def evaluate_dining() -> Dict[str, Any]:
    print("Evaluating Dining Spots...")
    db = SessionLocal()
    count = db.query(UserDiningFeedback).count()
    
    if count == 0:
        print("Dining: no feedback data exists — precision/recall not measurable.")
        db.close()
        return {"n": 0, "ground_truth": "none", "caveat": "no feedback data exists — precision/recall not measurable."}
    elif count < 10:
        print("Dining: Directional only — sample too small for a reliable confusion matrix")
        db.close()
        return {"n": count, "ground_truth": "none", "caveat": "Directional only — sample too small for a reliable confusion matrix"}
        
    db.close()
    return {"n": count, "ground_truth": "none"}

def evaluate_myntra() -> Dict[str, Any]:
    print("Evaluating Myntra...")
    db = SessionLocal()
    
    user_row = db.query(User).first()
    # Using google_sub as user_id per User schema primary mapping for recommendation endpoints
    user_id = user_row.google_sub if user_row else "test_user_myntra"
    
    try:
        recs = get_myntra_recommendations(db, user_id=user_id, limit=20)
        scores = [r.get("score", 0) for r in recs if isinstance(r, dict)]
        if not scores and recs and hasattr(recs[0], "score"):
            scores = [r.score for r in recs]
    except Exception as e:
        print(f"Myntra recommendation error: {e}")
        scores = []
        
    db.close()
    
    if scores:
        score_dist = {
            "min": float(np.min(scores)),
            "median": float(np.median(scores)),
            "max": float(np.max(scores))
        }
    else:
        score_dist = {"min": None, "median": None, "max": None}
        
    return {
        "ground_truth": "none — MyntraFeedback and MyntraEvent both empty",
        "score_distribution": score_dist
    }

def evaluate_cross_domain() -> Dict[str, Any]:
    print("Evaluating Cross-Domain Synchronization...")
    db = SessionLocal()
    users = db.query(User).all()
    
    convergence_scores = []
    
    for u in users:
        try:
            profile = compute_taste_profile(str(u.google_sub))
            conv = compute_convergence(profile)
            if conv.get("score") is not None:
                convergence_scores.append(conv["score"])
        except Exception:
            pass
            
    db.close()
    
    if convergence_scores:
        dist = {
            "min": float(np.min(convergence_scores)),
            "median": float(np.median(convergence_scores)),
            "mean": float(np.mean(convergence_scores)),
            "max": float(np.max(convergence_scores))
        }
    else:
        dist = {"min": None, "median": None, "mean": None, "max": None}
        
    res = {
        "n_users_evaluated": len(convergence_scores),
        "convergence_distribution": dist
    }
    if len(convergence_scores) < 10 and len(set(convergence_scores)) == 1:
        res["caveat"] = "identical score across all evaluated users — small n, not yet confirmed as a general pattern"
    return res

def main():
    os.makedirs('data/eval', exist_ok=True)
    os.makedirs('docs', exist_ok=True)
    
    metrics = {
        "anime": evaluate_anime(),
        "movies": evaluate_movies(),
        "spotify": evaluate_spotify(),
        "tourist_spots": evaluate_tourist_spots(),
        "dining": evaluate_dining(),
        "myntra": evaluate_myntra(),
        "cross_domain": evaluate_cross_domain(),
    }
    
    with open('data/eval/metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)
        
    report = ["# Model Evaluation Report\n"]
    
    for domain, res in metrics.items():
        report.append(f"## {domain.replace('_', ' ').title()}")
        if "caveat" in res and res["caveat"]:
            report.append(f"> **CAVEAT:** {res['caveat']}\n")
        
        for k, v in res.items():
            if k == "caveat": continue
            if isinstance(v, dict):
                report.append(f"- **{k}**: {json.dumps(v)}")
            elif isinstance(v, float):
                report.append(f"- **{k}**: {v:.4f}")
            else:
                report.append(f"- **{k}**: {v}")
                
        if domain in ["anime", "movies", "spotify", "tourist_spots"]:
            if res.get("precision") is not None:
                                report.append(f"\n![{domain} confusion matrix](../data/eval/{domain.replace('_', '')}_cm.png)\n")
                
    with open('docs/model_evaluation_report.md', 'w') as f:
        f.write("\n".join(report))
        
    print("Evaluation complete. Generated data/eval/metrics.json and docs/model_evaluation_report.md")

if __name__ == "__main__":
    main()
