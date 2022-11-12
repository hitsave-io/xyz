-- Include `result_json` column on evals.

ALTER TABLE evals
    ADD COLUMN result_json JSONB;
