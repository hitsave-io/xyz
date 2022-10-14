-- Users of the HitSave system.

-- Intention is to eventually extend this concept so that users are part of larger teams which can 
-- share data.

CREATE TABLE IF NOT EXISTS users (
    id              UUID            DEFAULT uuid_generate_v4() PRIMARY KEY,
    email           VARCHAR(100)    NOT NULL UNIQUE,
    create_dt       TIMESTAMPTZ     NOT NULL DEFAULT current_timestamp,
    update_dt       TIMESTAMPTZ     NOT NULL DEFAULT current_timestamp
);

CREATE INDEX users_email ON users (email);

CREATE TABLE IF NOT EXISTS api_keys (
    user_id         UUID            NOT NULL REFERENCES users(id),
    label           VARCHAR(100)    NOT NULL, -- mnemonic identifying reference for this key (e.g. "personal laptop")
    key             VARCHAR(64)     NOT NULL PRIMARY KEY,
    create_dt       TIMESTAMPTZ     NOT NULL DEFAULT current_timestamp
);

CREATE INDEX api_keys_user_id ON api_keys (user_id);

ALTER TABLE evals ADD COLUMN user_id UUID NOT NULL REFERENCES users(id);

-- Auth function to be used in queries for API Key-protected resources.
CREATE OR REPLACE FUNCTION auth_api_key(api_key VARCHAR(64))
    RETURNS SETOF users
    AS
$BODY$
BEGIN
    RETURN QUERY SELECT u.* FROM users u JOIN api_keys ak ON u.id = ak.user_id WHERE ak.key = $1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Invalid key %', $1 USING ERRCODE = 'invalid_password';
    END IF;

    RETURN;
END;
$BODY$
LANGUAGE plpgsql;
