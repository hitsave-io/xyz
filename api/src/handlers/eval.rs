use crate::extractors::with_blob::WithBlob;
use crate::middlewares::auth::Auth;
use crate::models::eval::{Eval, EvalError};
use crate::persisters::{eval::EvalInsert, Persist, Query};
use crate::state::AppState;
use actix_web::{error, get, put, web, Result};

impl From<EvalError> for actix_web::Error {
    fn from(e: EvalError) -> Self {
        match e {
            EvalError::NotFound(e) => {
                log::error!("not found: {:?}", e);
                error::ErrorNotFound("evals not found for params")
            }
            EvalError::Sqlx(e) => {
                log::error!("sql error: {:?}", e);
                error::ErrorInternalServerError("unknown error")
            }
            EvalError::Unauthorized => error::ErrorUnauthorized("unauthorized"),
        }
    }
}

#[derive(Deserialize, Debug)]
pub struct Params {
    pub fn_key: Option<String>,
    pub fn_hash: Option<String>,
    pub args_hash: Option<String>,
    pub poll: Option<bool>,
}

#[get("")]
async fn get_by_params(
    params: web::Query<Params>,
    auth: Auth,
    state: AppState,
) -> Result<web::Json<Vec<Eval>>, error::Error> {
    let _api_key = auth.allow_only_api_key()?;

    let res = params.fetch(Some(&auth), &state).await?;
    Ok(web::Json(res))
}

// TODO: get rid of the slash
#[put("/")]
async fn put(
    insert: WithBlob<EvalInsert>,
    auth: Auth,
    state: AppState,
) -> Result<String, error::Error> {
    let _api_key = auth.allow_only_api_key()?;

    let res = insert.persist(Some(&auth), &state).await?;

    Ok(res.to_string())
}

pub fn init(cfg: &mut web::ServiceConfig) {
    // cfg.service(get_by_id);
    cfg.service(get_by_params);
    cfg.service(put);
}
