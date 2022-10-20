#![feature(try_trait_v2)]
#![feature(result_option_inspect)]

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
#[macro_use]
extern crate lazy_static;

pub mod config;
pub mod handlers;
pub mod middlewares;
pub mod models;
pub mod msg_pack;
pub mod persisters;
pub mod state;

use config::Config;

lazy_static! {
    pub static ref CONFIG: Config = Config::parse_from_env();
}
