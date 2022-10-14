use super::{user_dao::IUser, AddUser};
use crate::state::AppState;
use actix_web::{error, put, web, Responder, Result};
use log::error;

#[put("/")]
async fn put(form: web::Json<AddUser>, state: AppState) -> Result<impl Responder> {
    let form = form.into_inner();

    let res = state.get_ref().insert_user(&form).await;

    match res {
        Ok(Some(user)) => Ok(web::Json(user)),
        Ok(None) => Err(error::ErrorInternalServerError("unknown error")),
        Err(sqlx::Error::Database(ref e)) => {
            error!("error inserting to database: {:?}", res);

            if e.code() == Some(std::borrow::Cow::Borrowed("23505")) {
                Err(error::ErrorBadRequest("email already exists"))
            } else {
                Err(error::ErrorInternalServerError("unknown error"))
            }
        }
        Err(_) => {
            error!("error inserting to database: {:?}", res);
            Err(error::ErrorBadRequest("could not insert new user"))
        }
    }
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(put);
}
