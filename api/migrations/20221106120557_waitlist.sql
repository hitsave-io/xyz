-- Table storing the waitlist from the landing page.

CREATE TABLE IF NOT EXISTS waitlist (
    id              UUID            DEFAULT uuid_generate_v4() PRIMARY KEY,
    email           VARCHAR(100)    UNIQUE,
    create_dt       TIMESTAMPTZ     NOT NULL DEFAULT current_timestamp
);
