use crate::middlewares::api_auth::Auth;
use crate::persisters::Query;
use crate::state::AppState;
use actix_web::{
    get,
    web::{self, Path},
    Error, HttpResponse,
};

#[derive(Deserialize, Debug)]
pub struct BlobParams {
    pub content_hash: String,
}

#[get("/{content_hash}")]
async fn get_blob(
    content_hash: Path<BlobParams>,
    auth: Auth,
    state: AppState,
) -> Result<HttpResponse, Error> {
    println!("{:?}", content_hash);
    let blob = content_hash.fetch(Some(&auth), &state).await?;
    Ok(blob)
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(get_blob);
}
