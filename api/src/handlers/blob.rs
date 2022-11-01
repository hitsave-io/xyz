use crate::extractors::with_blob::WithBlob;
use crate::middlewares::api_auth::Auth;
use crate::persisters::blob::BlobInsert;
use crate::persisters::{Persist, Query};
use crate::state::AppState;
use actix_web::{
    error, get, head, put,
    web::{self, Path},
    Error, HttpResponse,
};

#[derive(Deserialize, Debug)]
pub struct BlobParams {
    pub content_hash: String,
}

#[derive(Deserialize, Debug)]
pub struct BlobParamsHead {
    pub content_hash: String,
}

#[get("/{content_hash}")]
async fn get_blob(
    content_hash: Path<BlobParams>,
    auth: Auth,
    state: AppState,
) -> Result<HttpResponse, Error> {
    let blob = content_hash.fetch(Some(&auth), &state).await?;
    Ok(blob)
}

#[head("/{content_hash}")]
async fn head_blob(
    content_hash: Path<BlobParamsHead>,
    auth: Auth,
    state: AppState,
) -> Result<HttpResponse, Error> {
    let _blob = content_hash.fetch(Some(&auth), &state).await?;
    Ok(HttpResponse::Ok().into())
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
    cfg.service(head_blob);
    cfg.service(put_blob);
}
