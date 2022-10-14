-- Initial PostgreSQL database schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS evals (
    id              UUID            DEFAULT uuid_generate_v4() PRIMARY KEY,
    fn_key          TEXT            NOT NULL,
    fn_hash         VARCHAR(64)     NOT NULL,
    args            JSONB,
    args_hash       VARCHAR(64)     NOT NULL,
    result          BYTEA           NOT NULL,
    create_dt       TIMESTAMPTZ     NOT NULL DEFAULT current_timestamp
);
