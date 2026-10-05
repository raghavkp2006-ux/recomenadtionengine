Apply this migration manually to Render Postgres after reviewing the SQL.
Use a terminal with `psql` installed and access to the database.
Set `DATABASE_URL` to the target Render Postgres connection string in that terminal.
From the repository root, run: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/migrations/001_add_user_theme.sql`.
The Postgres-only statement is idempotent; verify the `users.theme` column afterward.
