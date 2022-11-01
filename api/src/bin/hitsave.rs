#[macro_use]
extern crate lazy_static;

use actix_web::{error, middleware, web, App, HttpServer, Result};
use hitsave_api::config::{Config, Opts};
use hitsave_api::{handlers, msg_pack};

lazy_static! {
    pub static ref CONFIG: Config = Config::parse_from_env();
}

#[actix_rt::main]
async fn main() -> std::io::Result<()> {
    let (_handle, _opt) = Opts::parse_from_args();
    let config = &*CONFIG;
    let state = config.clone().into_state().await;
    let state2 = state.clone();

    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(state.clone()))
            .app_data(state.clone())
            .app_data(msg_pack::MsgPackConfig::default().limit(4_294_967_296))
            .app_data(web::PathConfig::default())
            .app_data(web::JsonConfig::default())
            .app_data(web::QueryConfig::default())
            .app_data(web::FormConfig::default())
            .wrap(middleware::Compress::default())
            .wrap(middleware::Logger::default())
            .default_service(web::route().to(not_found))
            .service(web::scope("/blob").configure(handlers::blob::init))
            .service(web::scope("/eval").configure(handlers::eval::init))
            .service(web::scope("/user").configure(handlers::user::init))
            .service(web::scope("/api_key").configure(handlers::api_key::init))
    })
    .workers(1)
    .keep_alive(std::time::Duration::from_secs(300))
    .bind(("0.0.0.0", state2.config.port))?
    .run()
    .await
}

async fn not_found() -> Result<&'static str> {
    Err(error::ErrorNotFound("route not found"))
}
