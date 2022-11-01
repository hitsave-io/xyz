-- Add timing information to evals.

ALTER TABLE evals
    ADD COLUMN start_time TIMESTAMPTZ NOT NULL,
    ADD COLUMN elapsed_process_time BIGINT NOT NULL;
