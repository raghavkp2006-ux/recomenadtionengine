# Myntra integration architecture

The Manifest V3 extension observes permitted Myntra pages only after collection is enabled. Adapter parsers normalize product, search, listing, wishlist, cart, and visible-order content. Events are fingerprint-deduplicated, queued in extension storage, and uploaded in batches. Failed uploads remain queued with exponential backoff.

The FastAPI router validates events, associates them with the authenticated user, and stores raw events plus stable page-derived product records. A profile service applies configurable event weights and time decay. The recommender ranks only products that were already captured from accessible pages; it does not invent a catalog or claim availability.

Product dwell time is recorded on navigation or page exit and bucketed from `very_short` to `very_long`. Short views remain neutral rather than being treated as negative feedback. Myntra requests emit structured route/status/duration logs without page content or authentication data.

Myntra profile data is returned in a dedicated `myntra` namespace of the cross-domain profile, so fashion preferences never distort music, anime, or movie genre vectors.

On product pages the extension may show a dismissible recommendation panel. Its entries come solely from `/myntra/recommendations`, which ranks previously observed products. The assistant helper uses the same candidates and can only explain their supplied fields; it never invents products, availability, prices, ratings, brands, or URLs.

For the final local browser verification sequence, see `docs/myntra-e2e-checklist.md`.
