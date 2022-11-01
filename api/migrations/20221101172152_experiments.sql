-- Add experiment boolean flag to evals table.

ALTER TABLE evals
    ADD COLUMN is_experiment BOOL NOT NULL DEFAULT FALSE;
