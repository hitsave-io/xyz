extern crate sqlx;

use hitsave_api::config::format;
use nonblock_logger::{log::LevelFilter, BaseFilter, BaseFormater, NonblockLogger};
use sqlx::{migrate::Migrator, pool::Pool, postgres::Postgres};
use std::env;
use std::io::{Error, ErrorKind};

static MIGRATOR: Migrator = sqlx::migrate!();

#[actix_rt::main]
async fn main() -> std::io::Result<()> {
    let formater = BaseFormater::new()
        .local(true)
        .color(true)
        .level(4)
        .formater(format);

    let filter = BaseFilter::new()
        .starts_with(true)
        .notfound(true)
        .max_level(LevelFilter::Info);
    let _handle = NonblockLogger::new()
        .filter(filter)
        .unwrap()
        .formater(formater)
        .log_to_stdout()
        .map_err(|e| eprintln!("failed to init nonblock_logger: {:?}", e))
        .unwrap();

    dotenv::dotenv().ok();

    let mut env_vars: std::collections::HashMap<String, String> = env::vars().collect();

    // Build the database URL from the various environment variables and secrets.
    let database_user = env_vars
        .remove("POSTGRES_USER")
        .expect("no database user environment variable present");
    let database_password_file = env_vars
        .remove("POSTGRES_PASSWORD_FILE")
        .expect("no database password file environment variable present");
    let database_host = env_vars
        .remove("POSTGRES_HOST")
        .expect("no database host environment variable present");
    let database_port = env_vars
        .remove("POSTGRES_PORT")
        .expect("no database port environment variable present");
    let database_name = env_vars
        .remove("POSTGRES_DB")
        .expect("no database name environment variable present");
    let database_password = std::fs::read_to_string(database_password_file)
        .expect("could not read database password file; does it exist?");
    let database_url = format!(
        "postgres://{}:{}@{}:{}/{}",
        database_user, database_password, database_host, database_port, database_name
    );

    let pool = Pool::<Postgres>::connect(&database_url)
        .await
        .map_err(|e| {
            Error::new(
                ErrorKind::NotFound,
                format!("unable to connect to db: {}", e),
            )
        })?;

    MIGRATOR.run(&pool).await.map_err(|e| {
        Error::new(
            ErrorKind::Other,
            format!("error: migrating database: {}", e),
        )
    })?;

    log::info!("successfully migrated database");

    Ok(())
}
