-- Postgres only; idempotent and safe to re-run. Apply manually after review.
ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR DEFAULT 'dark';
