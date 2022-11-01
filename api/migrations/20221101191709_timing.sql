-- Add number of `accesses` to evals.

ALTER TABLE evals
    ADD COLUMN start_time TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    ADD COLUMN elapsed_process_time BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN accesses BIGINT NOT NULL DEFAULT 1;

-- Remove the temporary default constraints we used to add the columns.
ALTER TABLE evals
    ALTER COLUMN start_time DROP DEFAULT,
    ALTER COLUMN elapsed_process_time DROP DEFAULT;
