use serde::{Deserialize, Serialize};
use sqlx::types::JsonValue;

// https://docs.rs/sqlx/0.5.7/sqlx/trait.FromRow.html
// Extend derive(FromRow): https://github.com/launchbadge/sqlx/issues/156

#[derive(Serialize, Deserialize)]
pub struct Eval {
    pub fn_key: String,
    pub fn_hash: String,
    pub args: Option<JsonValue>,
    pub args_hash: String,
    pub content_hash: String,
}

#[derive(Debug)]
pub enum EvalError {
    Unauthorized,
    NotFound(sqlx::Error),
    Sqlx(sqlx::Error),
}
