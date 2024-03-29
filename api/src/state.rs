pub type SqlPool = sqlx::PgPool;
pub type PoolOptions = sqlx::postgres::PgPoolOptions;

use crate::config::Config;
use crate::persisters::s3store::S3Store;

#[derive(Clone)]
pub struct State {
    // TODO: use lazy_static! to make `Config` available everywhere, not just
    // the `State` struct passed into the web server
    pub config: Config,
    pub db_conn: SqlPool,
    pub s3_store: S3Store,
}

pub type AppStateRaw = std::sync::Arc<State>;
pub type AppState = actix_web::web::Data<AppStateRaw>;
