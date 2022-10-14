# HitSave API

The server for managed Hitsave.

## sqlx-cli

cargo install sqlx-cli --git

## Usage

1. Create a Postgres database called Hitsave.
2. Make a .env file in the root directory (see .env.template) containing
   a connection string for the DB, a port number for the server to
   listen at and a `jwt_priv` key with a random hex value (this is used in
   signing JWTs). In production environments, these variables should be
   set directly on the environment.
3. Ensure you have sqlx-cli installed: `cargo install sqlx-cli`.
4. Run `sqlx migrate run`.
5. Run the binary (`cargo build` or `cargo run` etc.)
6. Use the verbosity flags for different logging levels (-v, -vv, -vvv,
   etc).
7. To generate new database migrations, run `sqlx migrate add [name]`,
   then open the generated sql file in `migrations` directory. Once
   populated, run `sqlx migrate run`. See https://github.com/launchbadge/sqlx
   for detailed usage.

## Note

1. The sqlx query macros will connect to the database represented by
   `DATABASE_URL` in .env. You can consider using the non-statically-checked
   versions of the queries instead, but the macros are better, because
   they connect to the DB at compile time and check that the queries
   work.
