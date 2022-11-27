-- Add geo data (country, region, city) to pageload tracker.

ALTER TABLE pageloads
    ADD COLUMN country VARCHAR(2),
    ADD COLUMN region VARCHAR(3),
    ADD COLUMN city VARCHAR(32);
