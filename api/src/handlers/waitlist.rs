use crate::persisters::Persist;
use crate::state::AppState;
use actix_web::{put, web, HttpResponse, Responder, Result};

#[derive(Deserialize, Debug)]
pub struct WaitlistInsert {
    pub email: String,
}

#[put("")]
async fn put_user(form: web::Json<WaitlistInsert>, state: AppState) -> Result<impl Responder> {
    let waitlist_insert = form.into_inner();
    let _id = waitlist_insert.persist(None, &state).await?;
    Ok(HttpResponse::Ok())
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(put_user);
}
