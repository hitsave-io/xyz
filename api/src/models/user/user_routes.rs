use super::{user_dao::IUser, AddUser, User, UserError};
use crate::state::AppState;
use actix_web::{error, put, web, Error, Result};

impl From<UserError> for Error {
    fn from(e: UserError) -> Self {
        match e {
            UserError::AlreadyExists => error::ErrorBadRequest("email already exists"),
            UserError::Sqlx(_) => {
                error::ErrorInternalServerError("unknown error: could not insert new user")
            }
        }
    }
}

#[put("/")]
async fn put(form: web::Json<AddUser>, state: AppState) -> Result<web::Json<User>> {
    let form = form.into_inner();

    let res = state.get_ref().insert_user(&form).await?;

    Ok(web::Json(res))
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(put);
}
