# Myntra Integration Architecture Audit

## Scope and repository state

This audit was completed before modifying the application's architecture, as required by the implementation plan. The working directory now contains the repository identified in that plan at commit `5ef64c9` (`feat: add places recommendations to dashboard, wire real convergence data, fix hardcoded login URLs`).

The application is a FastAPI backend with a Vite/React frontend. It currently supports Spotify, Anime/AniList, movies, tourist spots, and dining. No browser extension, Myntra router, Myntra model, Myntra service, or Myntra test fixtures currently exist.

## Existing authentication and session flow

- `routers/google_auth.py` implements Google OAuth and upserts the user record through `database.upsert_google_user`.
- `services/auth.py` signs a `session` cookie with `itsdangerous.URLSafeSerializer`; `get_current_user_id` is the shared FastAPI dependency that validates it.
- `main.py` exposes `GET /auth/me` and applies an HTTP-only, secure, `SameSite=None` session cookie in the Google callback.
- Optional Spotify and AniList connections are linked to the authenticated application user through `get_current_user_id` and signed OAuth state.
- `frontend/src/api.ts` sends frontend requests with `credentials: "include"`.

### Implication for the extension

The extension must not read, copy, or store the session cookie. Its connection flow needs a deliberate backend-issued, revocable extension authorization mechanism after the user completes the existing backend login in a normal browser page. The first implementation phase must choose and document that handoff before extension uploads are enabled; directly relying on a third-party-page content script to send the existing cookie is not reliable or appropriate.

## Database architecture

- `database.py` owns one SQLAlchemy declarative `Base`, engine, `SessionLocal`, and `get_db` dependency.
- `DATABASE_URL` selects PostgreSQL; otherwise the app uses local SQLite (`spotify_tokens.db`).
- `init_db()` runs `Base.metadata.create_all()` at import and during FastAPI startup, with limited inline SQLite migrations for older Spotify and movie tables.
- Existing event-like storage is `SpotifyPlayEvent`, which uses a database unique constraint for deduplication.
- JSON values are stored as JSON-encoded `String` fields in the current schema.

### Data-model conventions and risks

- User identifiers are not fully consistent: `User.id` is an integer Google-user record, while several domain tables store `String` IDs. `UserSpotFeedback` and `UserDiningFeedback` reference `users.google_sub`, yet Google sessions currently contain the numeric `User.id` as a string. New Myntra tables must consistently use the authenticated session ID produced by `get_current_user_id` and avoid perpetuating this ambiguity.
- There is no migration framework. Initial Myntra tables can be introduced through SQLAlchemy metadata creation, but production schema change management should be addressed before a production rollout.

## Router and API conventions

- Routers live in `routers/` and are registered explicitly in `main.py`.
- Feature routers use an `APIRouter` prefix and tags, Pydantic request/response models, `Depends(get_current_user_id)` for protected routes, and `Depends(get_db)` when a scoped SQLAlchemy session is needed.
- Router-level errors are currently ordinary FastAPI `HTTPException` values with `detail`; there is no shared structured error envelope or request-ID middleware.
- CORS is configured in `main.py` from `ALLOWED_ORIGINS` or local frontend origins, with credentials enabled.

### Implication for Myntra routes

`routers/myntra.py` should follow the existing dependency pattern, but introduce a scoped error helper/exception handler and response models so its specified error contract can be implemented without changing unrelated APIs. CORS must be extended only after the extension origin and authorization transport are decided; Manifest V3 content scripts should not force broad origins or cookie access.

## Profile and recommendation architecture

- `services/taste_profile.py` is the central cross-domain aggregator. `compute_taste_profile()` merges Spotify, anime likes, AniList history, and movie signals, then emits domain crosswalks for anime, tourism, dining, and movies.
- `routers/taste.py` exposes this aggregate at `GET /taste-profile`.
- `routers/tourist_spots.py` and `routers/dining.py` invoke the shared profile service and pass its output into feature-specific deterministic recommendation services.
- `routers/anime.py` and `routers/movie.py` use profile-derived boost maps to re-rank existing candidates.
- Domain data/retrieval and ranking logic are generally kept in `services/`, while HTTP validation remains in routers.

### Implication for Myntra profiles and recommendations

Myntra must add a `myntra` namespace to the `breakdown` returned by `compute_taste_profile()` and preserve every existing key. A dedicated `services/myntra_profile.py` should build Myntra attributes from raw events; `services/myntra_recommender.py` should deterministically rank only stored/approved candidate products. No external/private Myntra product API should be added.

## Frontend architecture

- `frontend/` is a Vite + React + TypeScript application.
- `frontend/src/api.ts` is the shared typed-ish API wrapper and already uses cookie credentials for the backend.
- Dashboard components fetch category recommendations through this API wrapper.
- The current `connections` client type is stale: it expects a `location` value while the backend returns `google`, `spotify`, and `anilist`.

### Implication for Myntra UI

The initial popup/options UI should be isolated in `extension/`, not folded into the existing React frontend. If the dashboard later displays Myntra data, add it through `frontend/src/api.ts` and existing dashboard component patterns, after backend endpoints and contracts are tested.

## Deployment and configuration

- `Dockerfile` installs `requirements.txt` and runs Uvicorn on the platform port.
- `docker-compose.yml` runs backend and frontend locally.
- `render.yaml` defines backend and static frontend services plus PostgreSQL.
- `requirements.txt` includes FastAPI, SQLAlchemy, psycopg2, and related runtime dependencies; no rate-limit or migration package exists.
- The README documents local SQLite and production PostgreSQL, but references deployment details that differ from the current Render configuration.

## Test and CI architecture

- Python tests are in `tests/` and use `pytest`, FastAPI `TestClient`, dependency overrides for authenticated users, direct SQLite sessions, and mocks for external HTTP calls.
- Representative patterns are in `tests/test_taste_profile.py` and `tests/test_tourist_spots.py`.
- There is no extension test setup or shared JSON contract schema.
- The only GitHub workflow, `.github/workflows/frontend-redesign_polytaste.yml`, builds/deploys the frontend; it does not run backend tests, extension tests, contract tests, or build a backend image.

## Exact files planned for modification

The following list is deliberately scoped to the initial backend and extension phases; later files will be added only when their respective phase begins.

| Purpose | Files |
| --- | --- |
| Register Myntra functionality and configuration | `main.py`, `database.py`, `.env.example`, `requirements*.txt` only if a required dependency is introduced |
| Backend API, persistence, validation, and profiling | `routers/myntra.py` (new), `services/myntra_events.py` (new), `services/myntra_profile.py` (new), `services/myntra_recommender.py` (new), `services/myntra_agent.py` (new), `services/taste_profile.py` |
| Database models | `models/myntra.py` (new) or equivalent model definitions imported by `database.py`; the preferred choice will be confirmed in Phase 2 after avoiding duplicate SQLAlchemy bases |
| Backend tests and fixtures | `tests/test_myntra_*.py` (new), `data/myntra/*.csv` (new) |
| Browser extension | `extension/manifest.json`, `extension/src/**`, `extension/tests/**`, `extension/package.json`, `extension/README.md`, `extension/.env.example` (all new) |
| Documentation and automation | `docs/myntra-architecture.md` (new), `docs/myntra-api.md` (new), `README.md`, `.github/workflows/frontend-redesign_polytaste.yml` or a new dedicated CI workflow |

## Implementation decisions for Phase 2

1. Use Pydantic schemas as the backend contract source and validate all event payloads server-side.
2. Store raw normalized event and product payload fields separately from the derived profile; enforce `event_id` uniqueness at the database layer.
3. Keep selector parsing, event construction, offline queueing, and API transport entirely inside the MV3 extension.
4. Do not inspect cookies, passwords, payment data, tokens, or undocumented Myntra endpoints. Page extraction is limited to user-visible/structured page data the user has authorized.
5. Write fixture-driven tests before claiming parser support for any Myntra page type.

## Audit conclusion

The repository architecture is suitable for a new domain module, but Phase 2 should first establish a consistent Myntra user-key strategy and an extension-safe authorization handoff. With those boundaries, the next step is to implement typed product/event schemas and SQLAlchemy models plus tests, then register the new router only after its ingestion contract is verified.
