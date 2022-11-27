-- Add auth tracking to pageloads table.

ALTER TABLE pageloads ADD COLUMN auth TEXT;
