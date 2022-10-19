-- Evals, with external byte storage.

-- The content_hash column is used to address external data stores, such as S3 to retrieve the
-- the underlying raw data.

ALTER TABLE evals 
    DROP COLUMN result CASCADE,
    ADD COLUMN content_hash CHAR(64) NOT NULL;
