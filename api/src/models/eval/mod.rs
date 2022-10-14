use serde::{Deserialize, Serialize};
use sqlx::types::JsonValue;

pub mod eval_dao;
pub mod eval_routes;

// https://docs.rs/sqlx/0.5.7/sqlx/trait.FromRow.html
// Extend derive(FromRow): https://github.com/launchbadge/sqlx/issues/156

#[derive(FromRow, Serialize, Deserialize, Debug)]
pub struct Eval {
    pub fn_key: String,
    pub fn_hash: String,
    pub args: Option<JsonValue>,
    pub args_hash: String,
    #[serde(with = "serde_bytes")]
    pub result: Vec<u8>,
}

#[derive(Debug)]
pub enum EvalError {
    NotFound(sqlx::Error),
    Sqlx(sqlx::Error),
}
