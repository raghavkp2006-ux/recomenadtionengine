# Myntra API

All routes except `GET /myntra/health` use the existing authenticated PolyTaste session. The server derives the user from that session; clients must not send a user ID.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/myntra/connection` | Read collection settings |
| POST | `/myntra/connection` | Enable collection and update category controls |
| POST | `/myntra/events` | Ingest one normalized event |
| POST | `/myntra/events/batch` | Ingest at most 100 normalized events |
| GET | `/myntra/events/status` | Event count and last event timestamp |
| GET | `/myntra/history` | Filtered event history |
| GET | `/myntra/history/products` | Distinct observed products |
| GET | `/myntra/profile` | Weighted Myntra profile |
| POST | `/myntra/profile/rebuild` | Rebuild the profile from raw events |
| GET | `/myntra/recommendations` | Rank products previously observed from pages |
| GET | `/myntra/assistant/recommendations` | Grounded, candidate-only outfit explanation |
| POST | `/myntra/feedback` | Record explicit product feedback |
| GET | `/myntra/export.csv` | Deterministic UTF-8 event export |
| DELETE | `/myntra/data` | Delete the caller's Myntra events, profile, feedback, and connection settings |

The extension only extracts page data the user can view. It does not read cookies, credentials, payment data, tokens, or private Myntra APIs.

Errors returned by `/myntra/*` use `{ "error": { "code", "message", "request_id", "details" } }`. Event ingestion is limited to 60 requests per authenticated user per minute in this process. The shared event contract is at `data/myntra/contracts/event.schema.json`.
