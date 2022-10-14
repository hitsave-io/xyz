use super::{
    api_key_dao::{IApiKey, InsertKey},
    ApiKey, ApiKeyError,
};
use crate::state::AppState;
use actix_web::{error, get, web, Error, Result};

impl From<ApiKeyError> for Error {
    fn from(e: ApiKeyError) -> Self {
        match e {
            ApiKeyError::InvalidEmail => error::ErrorBadRequest("unknown email address"),
            _ => error::ErrorInternalServerError("could not generate new API key"),
        }
    }
}

/// A request from a user to generate a new API key.
#[derive(Serialize, Deserialize, Debug)]
pub struct GenRequest {
    email: String,
    label: String,
}

#[get("/generate")]
async fn generate_new_api_key(
    form: web::Json<GenRequest>,
    state: AppState,
) -> Result<web::Json<ApiKey>> {
    let gen_req = form.into_inner();

    let api_key = ApiKey::random();

    let insert_key = InsertKey {
        email: gen_req.email,
        label: gen_req.label,
        key: &api_key.key,
    };

    state
        .get_ref()
        .insert_key(&insert_key)
        .await
        .inspect_err(|e| error!("could not insert new API key into database: {:?}", e))?;

    Ok(web::Json(api_key))
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(generate_new_api_key);
}
