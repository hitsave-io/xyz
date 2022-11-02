use crate::middlewares::api_auth::Auth;
use crate::models::eval::Eval;
use crate::persisters::Query;
use crate::state::AppState;
use actix_web::{get, web, Result};

#[derive(Deserialize, Debug)]
pub struct Params {
    pub count: i64,
}

#[get("")]
async fn get_experiments(
    params: web::Query<Params>,
    auth: Auth,
    state: AppState,
) -> Result<web::Json<Vec<Eval>>> {
    let evals = params.fetch(Some(&auth), &state).await?;
    Ok(web::Json(evals))
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(get_experiments);
}
