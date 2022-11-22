-- Add a boolean flag to the blobs table, indicating that a blob is public. 
-- A blob still always has a user id, indicating who "owns" it.

ALTER TABLE blobs 
    ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT false;
