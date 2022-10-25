use crate::middlewares::jwt_auth::AuthorizationService;
use crate::models::api_key::{ApiKey, ApiKeyError};
use crate::persisters::api_key::{IApiKey, InsertKey};
use crate::state::AppState;
use actix_web::{error, get, web, Error, Result};

impl From<ApiKeyError> for Error {
    fn from(e: ApiKeyError) -> Self {
        match e {
            ApiKeyError::Unauthorized => {
                error::ErrorUnauthorized("not authorized to generate new API key")
            }
            _ => error::ErrorInternalServerError("could not generate new API key"),
        }
    }
}

/// A request from a user to generate a new API key.
#[derive(Serialize, Deserialize, Debug)]
pub struct GenRequest {
    label: String,
}

#[get("/generate")]
async fn generate_new_api_key(
    form: web::Query<GenRequest>,
    state: AppState,
    auth: AuthorizationService,
) -> Result<String> {
    let gen_req = form.into_inner();

    let api_key = ApiKey::random();

    let insert_key = InsertKey {
        user_id: auth.claims.sub,
        label: gen_req.label,
        key: &api_key.key,
    };

    state
        .get_ref()
        .insert_key(&insert_key)
        .await
        .inspect_err(|e| error!("could not insert new API key into database: {:?}", e))?;

    Ok(api_key.key)
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(generate_new_api_key);
}