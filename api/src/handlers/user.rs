use crate::handlers::login::{login_handler, LoginError};
use crate::persisters::{
    user::{UserUpsert, UserUpsertError},
    Persist,
};
use crate::state::AppState;
use actix_web::{error, post, put, web, Error, Result};

impl From<UserUpsertError> for Error {
    fn from(e: UserUpsertError) -> Self {
        match e {
            UserUpsertError::AlreadyExists => error::ErrorBadRequest("email already exists"),
            UserUpsertError::Unreachable => {
                error::ErrorInternalServerError("unknown error: could not insert new user")
            }
            UserUpsertError::Sqlx(_) => {
                error::ErrorInternalServerError("unknown error: could not insert new user")
            }
        }
    }
}

#[derive(Deserialize)]
struct Login {
    code: String,
}

impl From<LoginError> for Error {
    fn from(e: LoginError) -> Self {
        match e {
            LoginError::GHComms(e) => {
                log::error!("GitHub comms error when attempting to log in user: {:?}", e);
                error::ErrorInternalServerError("unable to login with GitHub")
            }
            LoginError::JwtError(e) => {
                log::error!(
                    "error generating JWT when attempting to log in user: {:?}",
                    e
                );
                error::ErrorInternalServerError("unable to login with GitHub")
            }
            LoginError::UserInsert(e) => {
                log::error!(
                    "error inserting new user in DB when attempting to log in user: {:?}",
                    e
                );
                e.into()
            }
            LoginError::AccessTokenNotGranted => {
                log::error!(
                    "error retrieving GitHub access token when attempting to log in user: {:?}",
                    e
                );
                error::ErrorInternalServerError("unable to login with GitHub")
            }
            LoginError::UserInfoNotAvailable => {
                log::error!(
                    "error retrieving GitHub user info when attempting to log in user: {:?}",
                    e
                );
                error::ErrorInternalServerError(
                    "unable to login with GitHub; user information not available",
                )
            }
            LoginError::NoPrimaryEmail => {
                log::error!(
                    "error retrieving GitHub primary email when attempting to log in user: {:?}",
                    e
                );
                error::ErrorInternalServerError(
                    "unable to login with GitHub; primary email not available",
                )
            }
        }
    }
}

#[post("/login")]
async fn login(form: web::Query<Login>, state: AppState) -> Result<String> {
    // this is the step 4 endpoint. it needs to break out into login handler code, and
    // eventually respond with step 10 (JWT for python client to use in future as authentication
    // when requesting new API keys and stuff like that)
    let form = form.into_inner();
    let jwt = login_handler(form.code, &state).await?;
    Ok(jwt)
}

// TODO: this can be deleted once the real flow is built.
#[put("/")]
async fn put(form: web::Json<UserUpsert>, state: AppState) -> Result<web::Json<sqlx::types::Uuid>> {
    let insert = form.into_inner();

    let uuid = insert.persist(None, &state).await?;

    Ok(web::Json(uuid))
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(put);
    cfg.service(login);
}
