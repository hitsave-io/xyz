-- Table recording ownership of BLOBs.

CREATE TABLE IF NOT EXISTS blobs (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         UUID            NOT NULL REFERENCES users(id),
    content_hash    CHAR(64)        NOT NULL,
    UNIQUE (user_id, content_hash)
);

ALTER TABLE evals
    DROP COLUMN IF EXISTS content_hash CASCADE,
    ADD COLUMN IF NOT EXISTS blob_id BIGINT NOT NULL REFERENCES blobs(id);

