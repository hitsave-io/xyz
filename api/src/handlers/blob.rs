use crate::extractors::with_blob::WithBlob;
use crate::middlewares::api_auth::Auth;
use crate::persisters::blob::BlobInsert;
use crate::persisters::{Persist, Query};
use crate::state::AppState;
use actix_web::{
    error, get, put,
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

#[put("")]
async fn put_blob(
    insert: WithBlob<BlobInsert>,
    auth: Auth,
    state: AppState,
) -> Result<String, error::Error> {
    let res = insert.persist(Some(&auth), &state).await?;

    Ok(res.to_string())
}

pub fn init(cfg: &mut web::ServiceConfig) {
    cfg.service(get_blob);
    cfg.service(put_blob);
}
