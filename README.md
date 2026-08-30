# Poly_Taste — Cross-Domain Taste Recommendation Engine

A FastAPI application deployed to Azure Web App, providing content-based and cross-domain recommendations across five media/lifestyle domains: **Spotify (music)**, **Anime**, **Tourist Spots**, **Movies**, and **Restaurants/Cafes (Dining)**. A **Genre Crosswalk engine** unifies signal from all connected domains into a single personalized taste profile.

---

## Modules

### Myntra

User-controlled Myntra page activity integration. See [the extension README](extension/README.md), [API reference](docs/myntra-api.md), and [architecture](docs/myntra-architecture.md). It uses page-visible/structured data only and never accesses cookies or private Myntra endpoints.

### Auth / Session

The app uses a signed cookie session for authentication, established via Google Sign-In (keyed on `google_sub`). Spotify and AniList are optional secondary connections linked to this primary Google session to pull listening/watch data into the taste profile. They do not create or overwrite the session on their own.

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/google/login` | Sign in with Google (starts the app-wide login flow) |
| `GET` | `/auth/google/callback` | OAuth callback — verifies identity, sets session cookie |
| `GET` | `/auth/me` | Returns current `user_id` if logged in (401 otherwise) |
| `POST` | `/auth/logout` | Clears the session cookie |

---

### Spotify

Genre-profile content-based recommendations. Users can optionally connect their Spotify account to their Google session via OAuth to build a weighted genre fingerprint from their top artists.

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/spotify/login` | Connect Spotify account (links to existing Google session) |
| `GET` | `/spotify/callback` | OAuth callback — stores Spotify token for the current user |
| `GET` | `/spotify/top-tracks` | User's top 10 tracks |
| `GET` | `/spotify/recommendations` | Genre-profile track recommendations |
| `GET` | `/spotify/recommend/{track_id}` | **[Deprecated]** DNN similarity via `/audio-features` (unavailable for new apps since Nov 2024) |

---

### Anime

TF-IDF + AutoEncoder similarity over a Kitsu-sourced catalog, plus live data from AniList, YouTube, and Anime News Network.

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/anime/search?q=` | Substring title search on catalog |
| `GET` | `/anime/upcoming` | Upcoming anime (AniList GraphQL, Jikan fallback) |
| `GET` | `/anime/{mal_id}` | Single catalog entry |
| `GET` | `/anime/{mal_id}/recommend` | TF-IDF/AutoEncoder similarity recommendations. Add `?personalize=true` for cross-domain taste-boosted re-ranking |
| `GET` | `/anime/{mal_id}/reviews` | Review snippets (AniList, Jikan fallback) |
| `GET` | `/anime/{mal_id}/videos` | YouTube trailers/explainers — requires `YOUTUBE_API_KEY` |
| `GET` | `/anime/{mal_id}/news` | Anime News Network RSS articles filtered by title |
| `POST` | `/anime/{mal_id}/like` | Record a like (authenticated) |
| `DELETE` | `/anime/{mal_id}/like` | Remove a like (authenticated) |

#### Data Sources

- **Catalog**: Kitsu API (`services/jikan_client.py`) — run once locally or on a schedule to populate `data/raw/anime_catalog.json`
- **Upcoming / Reviews**: AniList public GraphQL API (`services/anilist_client.py`) — no API key required
- **Videos**: YouTube Data API v3 — requires `YOUTUBE_API_KEY` (see setup below)
- **News**: Anime News Network RSS feed — no API key required

---

### Tourist Spots

56 curated Chennai tourist spots across six categories, sourced via the Overpass API / OpenStreetMap. TF-IDF-based browsing and filtering, with crosswalk mapping from music/anime taste to spot categories.

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tourist-spots` | List spots, optionally filtered by category |
| `GET` | `/tourist-spots/recommendations` | Personalized recommendations (authenticated) |
| `GET` | `/tourist-spots/{place_id}` | Single spot detail |
| `POST` | `/tourist-spots/{place_id}/feedback` | Record like/dislike feedback (authenticated) |

---

### Movies

TF-IDF + cosine similarity over a TMDB-sourced catalog of 255 movies, with synthetic personal ratings (genre/keyword-biased placeholder data — see `scripts/generate_synthetic_ratings.py` for methodology) standing in for real user history until genuine per-user rating data is collected.

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/movie/{movie_id}/recommend` | Item-to-item content similarity. Add `?personalize=true` for cross-domain taste-boosted re-ranking |
| `POST` | `/movie/recommendations` | Taste-vector recommendations from `liked_ids`, or auto-seeded from rated movies (`personal_rating >= 7.0`) if omitted |

#### Data Sources

- **Catalog**: TMDB popular/top-rated endpoints (`scripts/fetch_movies.py`, `scripts/backfill_vote_average.py`)
- **Personal ratings**: Synthetic bootstrap data (`scripts/generate_synthetic_ratings.py`) — clearly flagged as placeholder in code, pending real user rating collection

---

### Restaurants / Cafes (Dining)

872 Chennai restaurants/cafes sourced via the Overpass API / OpenStreetMap, hardcoded into a static dataset and categorized into six dining categories. Extends the same TF-IDF/crosswalk pattern used by Tourist Spots.

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dining` | List dining spots, filterable by category and/or cuisine |
| `GET` | `/dining/recommendations` | Personalized recommendations from cross-domain taste profile (authenticated) |
| `GET` | `/dining/{place_id}` | Single dining spot detail |
| `POST` | `/dining/{place_id}/feedback` | Record like/dislike feedback (authenticated) |

#### Data Sources

- **Catalog**: Overpass API / OpenStreetMap export, ingested once via `scripts/build_restaurants_cafes.py` and seeded via `scripts/seed_dining_spots.py`

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/raghavkp2006-ux/Poly_Taste.git
cd Poly_Taste
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Required for | Where to get it |
|----------|-------------|-----------------|
| `GOOGLE_CLIENT_ID` | Google Sign-In | [console.cloud.google.com](https://console.cloud.google.com/) |
| `GOOGLE_CLIENT_SECRET` | Google Sign-In | Same app settings page |
| `GOOGLE_REDIRECT_URI` | Google Sign-In | Set to your frontend origin's callback, e.g. `http://localhost:5173/#id_token=` |
| `SPOTIFY_CLIENT_ID` | Spotify endpoints | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) |
| `SPOTIFY_CLIENT_SECRET` | Spotify endpoints | Same app settings page |
| `SPOTIFY_REDIRECT_URI` | Spotify OAuth | Set to `http://127.0.0.1:8000/spotify/callback` exactly. **Note:** Access the app via `http://127.0.0.1:8000`, not `localhost`. Spotify apps in Development Mode are capped at 5 test users — new teammates must be added as testers on the Spotify Developer Dashboard before they can authenticate. |
| `ANILIST_CLIENT_ID` | AniList connect | [anilist.co/settings/developer](https://anilist.co/settings/developer) |
| `ANILIST_CLIENT_SECRET` | AniList connect | Same app settings page |
| `ANILIST_REDIRECT_URI` | AniList OAuth | Set to `http://127.0.0.1:8000/anilist/callback` exactly |
| `TMDB_API_KEY` | Movie catalog fetch | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) — free Developer key |
| `SESSION_SECRET_KEY` | App authentication | Set to a random secure string in production |
| `YOUTUBE_API_KEY` | `/anime/{id}/videos` | [console.cloud.google.com](https://console.cloud.google.com/apis/library/youtube.googleapis.com) — enable YouTube Data API v3 |

> **YouTube quota note:** `search.list` costs 100 quota units per call. The free tier provides 10,000 units/day, supporting ~100 video searches/day.

- Each developer needs their own `GOOGLE_CLIENT_ID`/`SECRET`, `TMDB_API_KEY`, and `YOUTUBE_API_KEY`.
- Spotify credentials are shared under the project owner's Developer app — teammates authenticate as whitelisted test users rather than creating separate Spotify apps.
- Azure/production variables (database connection strings, etc.) are only needed for production deployment. The app automatically uses SQLite when these are absent locally.

### 3. Populate catalogs (one-time)

```bash
python services/jikan_client.py                # Anime catalog (Kitsu)
python scripts/fetch_movies.py                 # Movie catalog (TMDB)
python scripts/backfill_vote_average.py        # Movie vote_average backfill
python scripts/generate_synthetic_ratings.py   # Synthetic personal ratings
python scripts/seed_tourist_spots.py           # Tourist spots (from data/tourist_spots_chennai.json)
python scripts/seed_dining_spots.py            # Dining spots (from data/restaurants_cafes_chennai.json)
```

### 4. Run locally

```bash
python main.py
# or
uvicorn main:app --reload
```

To test the application flow:
1. Start the app and visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive Swagger UI, or launch the frontend.
2. Sign in with Google first (via `/auth/google/login`).
3. Once a session is established, you can optionally connect Spotify or AniList to pull in your taste data.

---

## Running Tests

```bash
pytest tests/ -v
```

All external HTTP calls are mocked in the test suite — no live API access or credentials are required to run tests.

---

## Architecture

- **FastAPI on Azure Web App** (Free F1 tier, Central India region)
- **Azure PostgreSQL Flexible Server** (Burstable B1ms, Dev/Test) → production database
- **SQLite** → local development database (auto-detected when Azure connection vars are absent)
- **Static JSON + hardcoded datasets** → Tourist Spots and Dining catalogs (Overpass/OpenStreetMap-sourced, ingested once via seed scripts)
- **PyTorch AutoEncoder** (1000→128→32 dims) → anime embeddings, trained offline; only NumPy-based inference runs in production (`torch`/`sentence-transformers` are dev-only dependencies, see `requirements-dev.txt`) to keep Azure build times low
- **TF-IDF + cosine similarity** → Movies, Tourist Spots, and Dining recommendations (appropriately sized for each catalog — no oversized ML architecture for small datasets)

> **Note:** Docker and AWS Lambda scaffolding exist elsewhere in this repo from an earlier deployment approach but are not currently used — the app is deployed on Azure as described above.
