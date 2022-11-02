use crate::middlewares::auth::Auth;
use crate::models::eval::Eval;
use crate::persisters::Query;
use crate::state::AppState;
use actix_web::{get, web, Result};

// TODO: implement filtering params like:
// after: Date
// before: Date
// project: ?
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
    println!("{:?}", auth);
    println!("{}", auth.is_api_key());
    println!("{}", auth.is_jwt());
    let _jwt = auth.allow_only_jwt()?;
    // let evals = params.fetch(Some(&auth), &state).await?;
    todo!()
    //Ok(web::Json((evals))
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(get_experiments);
}
