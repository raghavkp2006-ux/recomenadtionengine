# Local setup (Windows PowerShell)

Branch: `local-setup`. No deployment, push, or merge is required.

## Configuration

Copy `.env.example` to `.env` only if you do not already have a `.env`:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Supply your own OAuth credentials in the ignored `.env`. Keep its local settings
from `.env.example`: `ENV=local`, `DATABASE_URL=sqlite:///./local_polytaste.db`,
the listed CORS origins, and `FRONTEND_URL=http://127.0.0.1:5173`.
When `DATABASE_URL` is unset, the backend uses SQLite at `SQLITE_PATH`, defaulting
to `spotify_tokens.db`. The dedicated local database avoids changing that existing
database. Explicit process environment variables take precedence over `.env`.

Use `http://127.0.0.1:5173` in the browser. `localhost` and `127.0.0.1` have different
cookie hosts. `ENV=local` selects `Secure=False`, `SameSite=lax`; all other values
retain the existing `Secure=True`, `SameSite=none` behavior. Production configuration
and `render.yaml` are unchanged. Vite uses `/api` in development only and removes
that prefix when proxying to `http://127.0.0.1:8000`.

Register the exact local callbacks with the providers before using OAuth:

- Google: `http://127.0.0.1:8000/auth/google/callback`.
- Spotify: `http://127.0.0.1:8000/spotify/callback`.
- AniList: `http://127.0.0.1:8000/anilist/callback` (provider acceptance required).

The extension's required host permissions include the loopback backend. Its default
backend URL is local. An existing installation may have a saved Render URL that
overrides the default: set **Backend URL** to `http://127.0.0.1:8000` in Options and
save. Enable collection. If its unpacked ID differs from
`ehicjjjefimefanmlleacjhdmbfnobel`, add the actual `chrome-extension://<id>` origin
to `ALLOWED_ORIGINS` and restart the backend.

## Seed in this exact order

Run these commands from the repository root with the existing project `.venv`.
They use the dedicated local SQLite database and require no catalog API calls.
Movie, spot, dining, and anime artifacts are tracked. The Myntra CSV is ignored
and available on this machine; a fresh clone needs that CSV supplied separately.

```powershell
$env:ENV = 'local'
$env:DATABASE_URL = 'sqlite:///./local_polytaste.db'

# 1. Movies: committed TF-IDF metadata, retaining artifact IDs.
@'
import pickle, json
from database import SessionLocal, engine, Movie
assert engine.url.get_backend_name() == 'sqlite'
data = pickle.load(open('data/processed/movie_tfidf_matrix.pkl', 'rb'))
with SessionLocal() as db:
    for movie in data['metadata'].values():
        if db.query(Movie).filter_by(tmdb_id=movie['tmdb_id']).first():
            continue
        fields = {k: v for k, v in movie.items()
                  if k in Movie.__table__.columns.keys() and k != 'personal_rating'}
        fields['genres_json'] = json.dumps(movie.get('genres', []))
        db.add(Movie(**fields))
    db.commit()
    print('movies:', db.query(Movie).count())
'@ | .venv/Scripts/python.exe -

# 2. Tourist spots.
.venv/Scripts/python.exe scripts/seed_tourist_spots.py

# 3. Dining.
.venv/Scripts/python.exe scripts/seed_dining_spots.py

# 4. Myntra: existing local CSV, reproducible balanced sample.
.venv/Scripts/python.exe scripts/seed_myntra_products.py --csv data/myntra_seed/myntra_products.csv --limit 500

# 5. Anime: loaded directly from its committed embedding artifact, no SQL table.
@'
import pickle
data = pickle.load(open('data/processed/anime_embeddings.pkl', 'rb'))
assert data and all('embedding' in row and 'title' in row for row in data.values())
print('anime embeddings:', len(data))
'@ | .venv/Scripts/python.exe -

# Print every SQLite table count.
@'
from sqlalchemy import inspect, text
from database import engine
assert engine.url.get_backend_name() == 'sqlite'
with engine.connect() as connection:
    for name in inspect(engine).get_table_names():
        print(name, connection.execute(text('SELECT COUNT(*) FROM "' + name + '"')).scalar())
'@ | .venv/Scripts/python.exe -
```

Movie artifact personal ratings are excluded from the local seed because they are
not user-specific ratings. Existing `data/raw/anime_catalog.json` contains 100
detailed records on this machine; it is ignored and separate from the 14,976
committed embeddings. A fresh clone can run the backend with the embeddings, but
needs the raw catalog separately for detailed anime search records.

## Three launch commands

Run each in its own PowerShell terminal, starting at the repository root.

```powershell
# 1. Backend (.env selects local SQLite and HTTP cookies).
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# 2. Frontend.
Set-Location frontend; npm run dev -- --host 127.0.0.1 --port 5173 --strictPort

# 3. Open Chrome's extension manager.
Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' 'chrome://extensions'
```

In the extension manager, enable Developer mode and **Load unpacked**, selecting
this repository's `extension` directory. For an already loaded extension, click
Reload. There is no shell command that completes the Load unpacked file picker.

## Verification and current limits

Local HTTP verification passed: unauthenticated `/api/auth/me` returns 401 JSON;
the existing development `/auth/login` endpoint sets a `HttpOnly; SameSite=lax`
cookie without `Secure`; `/api/auth/me`, connections, preferences, taste profile,
convergence, Myntra profile and recommendations return 200. Logout clears the
session. Extension CORS preflight accepts the configured extension origin.
A synthetic product-view event was accepted by the direct loopback backend and
appeared in history through the frontend proxy. It is marked `local_verification`
in the dedicated local database; it is not evidence of browser capture.

Existing tests: 14 Myntra pytest tests passed, and 6 extension tests passed on
Node 20. SQLite fallback and production/default cookie settings were also checked.

Browser automation stopped because the Computer Use helper could not reliably
determine Chrome's current URL. Google OAuth login, rendered dashboard, unpacked
extension loading, and a real Myntra browser capture still require manual checks:

1. Open `http://127.0.0.1:5173`, sign in with Google after registering the callback,
   and complete/skip onboarding. Confirm `/api/auth/me` returns 200 in DevTools.
2. Confirm the dashboard loads its data and stays signed in after refreshing.
3. Reload/load the extension, save its local backend URL, and enable collection.
   Visit a Myntra product, sync, then check the local Fashion history for that item.
4. In DevTools, confirm extension requests use `http://127.0.0.1:8000`.

Hosted URLs remain in `render.yaml` (production CORS) and two legacy extension
diagnostic scripts.
Those scripts still target Render and must not be used for local verification.
The manifest and active backend URL default contain no Render origin.
