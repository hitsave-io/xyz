use super::{
    eval_dao::{IEval, QueryParams},
    Eval,
};
use crate::middlewares::api_auth::ApiAuthService;
use crate::msg_pack::MsgPack;
use crate::state::AppState;
use actix_web::{error, get, put, web, Result};
use sqlx::types::Uuid;

#[get("/{id}")]
async fn get_by_id(form: web::Path<String>, state: AppState) -> Result<MsgPack<Eval>> {
    let id = form.into_inner();
    let uuid = Uuid::parse_str(id.as_str()).map_err(|_| error::ErrorNotFound("invalid uuid"))?;

    let eval = state.get_ref().get_eval_by_id(uuid).await.map_err(|e| {
        error!("no such eval {:?}: {:?}", id.as_str(), e);
        error::ErrorNotFound(format!("eval not found for id {:?}", id.as_str()))
    })?;

    Ok(MsgPack(eval))
}

#[derive(Serialize)]
struct QueryResults {
    results: Vec<Eval>,
}

#[get("/")]
async fn get_by_params(
    form: web::Json<QueryParams>,
    auth: ApiAuthService,
    state: AppState,
) -> Result<MsgPack<QueryResults>, error::Error> {
    let params = form.into_inner();

    let evals = state
        .get_ref()
        .get_evals_by_params(params, &auth.key)
        .await
        .map_err(|e| {
            error!("error querying database {:?}", e);
            error::ErrorNotFound(format!("evals not found for params"))
        })?;

    Ok(MsgPack(QueryResults { results: evals }))
}

#[put("/")]
async fn put(
    form: MsgPack<Eval>,
    auth: ApiAuthService,
    state: AppState,
) -> Result<String, error::Error> {
    let form = form.into_inner();

    let res = state
        .get_ref()
        .insert_eval(&form, &auth.key)
        .await
        .map_err(|e| {
            error!("error inserting eval: {:?}", e);
            match e {
                sqlx::Error::Database(pge) => {
                    if pge.as_ref().code() == Some(std::borrow::Cow::Borrowed("28P01")) {
                        error::ErrorUnauthorized("invalid API key")
                    } else {
                        error::ErrorInternalServerError("unknwon error")
                    }
                }
                _ => error::ErrorInternalServerError(e),
            }
        })?;

    Ok(res)
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(get_by_id);
    cfg.service(get_by_params);
    cfg.service(put);
}
