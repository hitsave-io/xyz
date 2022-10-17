-- Update to users table to reflect sign-in with GitHub.

ALTER TABLE users 
    ADD COLUMN gh_id INT UNIQUE,
    ADD COLUMN gh_email VARCHAR(100) UNIQUE,
    ADD COLUMN gh_login VARCHAR(100) NOT NULL UNIQUE,
    ADD COLUMN gh_token VARCHAR(100),
    ADD COLUMN gh_avatar_url VARCHAR(60),
    ADD COLUMN email_verified BOOL,
    DROP COLUMN email CASCADE;

CREATE INDEX users_gh_email ON users (gh_email);
