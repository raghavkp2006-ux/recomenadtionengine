import json, csv, sqlite3, pickle, hashlib
from pathlib import Path
from collections import Counter
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
result = {}
history = []
files = []
for p in sorted((ROOT / 'Spotify Extended Streaming History').glob('Streaming_History_Audio_*.json')):
    rows = json.loads(p.read_text(encoding='utf-8'))
    history.extend(rows)
    files.append({'file': p.name, 'records': len(rows), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
valid = [r for r in history if r.get('master_metadata_album_artist_name')]
tracks = [r for r in history if r.get('spotify_track_uri') and r.get('master_metadata_track_name')]
artists = Counter(r['master_metadata_album_artist_name'] for r in valid)
timestamps = [r['ts'] for r in valid if r.get('ts')]
result['spotify_history'] = {'files':files, 'raw_events':len(history), 'artist_valid_events':len(valid), 'track_valid_events':len(tracks), 'unique_artists':len(artists), 'artists_at_least_5_plays':sum(n>=5 for n in artists.values()), 'unique_track_uris':len({r['spotify_track_uri'] for r in tracks}), 'min_timestamp':min(timestamps), 'max_timestamp':max(timestamps), 'hours_played_artist_valid':sum(r.get('ms_played',0) for r in valid)/3600000, 'example_fields': sorted(history[0]), 'duplicate_track_timestamp_events':len(tracks)-len({(r.get('ts'),r.get('spotify_track_uri')) for r in tracks})}
result['databases']={}
for name in ['local_polytaste.db','spotify_tokens.db']:
    con=sqlite3.connect(f'file:{(ROOT/name).as_posix()}?mode=ro',uri=True)
    tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    counts={t:con.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}
    movies={}
    if 'movies' in tables:
        movies['rated']=con.execute('SELECT COUNT(*) FROM movies WHERE personal_rating IS NOT NULL').fetchone()[0]
        movies['liked_at_least_7']=con.execute('SELECT COUNT(*) FROM movies WHERE personal_rating>=7').fetchone()[0]
        pairs=con.execute('SELECT personal_rating,vote_average FROM movies WHERE personal_rating IS NOT NULL AND vote_average IS NOT NULL').fetchall()
        if len(pairs)>1:
            a=np.array(pairs,dtype=float)
            movies['rating_popularity_correlation']=float(np.corrcoef(a.T)[0,1])
    result['databases'][name]={'counts':counts,'movie_ratings':movies}
    con.close()
result['catalogs']={}
for rel in ['data/tourist_spots_chennai.json','data/restaurants_cafes_chennai.json']:
    obj=json.loads((ROOT/rel).read_text(encoding='utf-8'))
    result['catalogs'][rel]={'type':type(obj).__name__,'count':len(obj),'keys':list(obj)[:8] if isinstance(obj,dict) else None}
for rel in ['data/raw/top_15000_anime.csv','data/myntra_seed/myntra_products.csv','data/myntra_seed/myntra_products_catalog.csv']:
    with (ROOT/rel).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); rows=list(reader)
        result['catalogs'][rel]={'rows':len(rows),'fields':reader.fieldnames}
        if 'anime' in rel: result['catalogs'][rel]['usable_text_rows']=sum(bool((r.get('synopsis') or '').strip() or (r.get('genres') or '').strip()) for r in rows)
for rel in ['data/processed/anime_embeddings.pkl','data/processed/movie_tfidf_matrix.pkl','data/eval/anime_dense_cache.pkl']:
    with (ROOT/rel).open('rb') as f: obj=pickle.load(f)
    if isinstance(obj,dict) and 'matrix' in obj:
        info={'shape':list(obj['matrix'].shape),'ids':len(obj['ids']),'rated_metadata':sum(v.get('personal_rating') is not None for v in obj['metadata'].values())}
    elif isinstance(obj,dict):
        info={'records':len(obj),'embedding_dim':len(next(iter(obj.values()))['embedding']),'fields':list(next(iter(obj.values()))),'genre_type':type(next(iter(obj.values())).get('genres')).__name__}
    else: info={'shape':list(obj.shape)}
    result['catalogs'][rel]=info
p=ROOT/'data/models/track_embeddings.json'
obj=json.loads(p.read_text(encoding='utf-8'))
result['catalogs'][str(p.relative_to(ROOT))]={'tracks':len(obj['tracks']),'embedding_dim':obj['embed_dim'],'tracks_with_genres':sum(bool(v.get('genres')) for v in obj['tracks'].values())}
result['saved_metrics']=json.loads((ROOT/'data/eval/metrics.json').read_text())
for rel in ['data/models/anime_model.pth','data/models/spotify_model.pth','data/eval/metrics.json']:
    p=ROOT/rel
    result.setdefault('artifacts',{})[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(OUT/'inventory.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
