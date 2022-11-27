-- Simple table for storing page loads.

CREATE TABLE IF NOT EXISTS pageloads (
    id          UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    route       TEXT        NOT NULL,
    user_agent  TEXT,
    referer     TEXT,
    ip          TEXT,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);
