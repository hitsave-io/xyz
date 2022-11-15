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

    let db_url = env::var("DATABASE_URL").map_err(|e| {
        Error::new(
            ErrorKind::InvalidData,
            format!("error: environment variable `DATABASE_URL`: {}", e),
        )
    })?;

    let pool = Pool::<Postgres>::connect(&db_url).await.map_err(|e| {
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
