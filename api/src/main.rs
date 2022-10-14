#![feature(try_trait_v2)]
#[macro_use]
extern crate nonblock_logger;
#[macro_use]
extern crate async_trait;
#[allow(unused_imports)]
#[macro_use]
extern crate validator;
#[macro_use]
extern crate sqlx;
#[macro_use]
extern crate serde;

use actix_web::{error, middleware, web, App, HttpServer, Result};
use config::{Config, Opts};

pub mod config;
pub mod middlewares;
pub mod models;
pub mod msg_pack;
pub mod state;

#[actix_rt::main]
async fn main() -> std::io::Result<()> {
    let (_handle, _opt) = Opts::parse_from_args();
    let state = Config::parse_from_env().into_state().await;
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
            .service(web::scope("/eval").configure(models::eval::eval_routes::init))
            .service(web::scope("/user").configure(models::user::user_routes::init))
            .service(web::scope("/api_key").configure(models::api_key::api_key_routes::init))
    })
    .keep_alive(std::time::Duration::from_secs(300))
    .bind(("0.0.0.0", state2.config.port))?
    .run()
    .await
}

async fn not_found() -> Result<&'static str> {
    Err(error::ErrorNotFound("route not found"))
}
