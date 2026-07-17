-- Runs once, on a fresh Postgres volume (docker-entrypoint-initdb.d).
-- The postgres image only auto-creates POSTGRES_DB (app); every other database
-- this stack needs must be created here, or it silently goes missing after a
-- `docker compose down -v`.

-- Langfuse (LLM tracing) keeps its own database.
CREATE DATABASE langfuse;

-- Dedicated database for the Postgres-backed RLS tests, so they never touch dev data.
CREATE DATABASE app_test;
