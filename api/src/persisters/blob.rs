use crate::handlers::blob::BlobParams;
use crate::middlewares::api_auth::Auth;
use crate::persisters::{s3store::StoreError, Query};
use crate::state::State;
use actix_web::{
    body::BodyStream, error, http::StatusCode, web::Path, Error, HttpResponse, HttpResponseBuilder,
};
use blake3::{Hash, HexError};

#[async_trait]
impl Query for Path<BlobParams> {
    type Resolve = HttpResponse;
    type Error = BlobError;

    async fn fetch(self, auth: Option<&Auth>, state: &State) -> Result<Self::Resolve, Self::Error> {
        let auth = auth.ok_or(BlobError::Unauthorized)?;
        let content_hash = self.into_inner().content_hash;

        // 1. Check the hash is valid.
        let hash = Hash::from_hex(&content_hash)?;

        // 2. Check postgres to make sure they are authed.
        let res = query!(
            r#"
                SELECT count(id) FROM blobs
                WHERE   content_hash = $1
                    AND user_id = user_from_key($2)
           "#,
            content_hash,
            auth.key
        )
        .fetch_one(&state.db_conn)
        .await?;

        if res.count != Some(1) {
            return Err(BlobError::Unauthorized);
        }

        // 3. Ping S3 for the BLOB and send it.
        let byte_stream = state.s3_store.retrieve_blob(hash).await?;
        let body_stream = BodyStream::new(byte_stream);
        let http_response = HttpResponseBuilder::new(StatusCode::OK).body(body_stream);
        Ok(http_response)
    }
}

pub enum BlobError {
    Unauthorized,
    InvalidHash,
    StoreError,
    Sqlx(sqlx::Error),
}

impl From<HexError> for BlobError {
    fn from(_: HexError) -> Self {
        BlobError::InvalidHash
    }
}

impl From<StoreError> for BlobError {
    fn from(_: StoreError) -> Self {
        BlobError::StoreError
    }
}

impl From<sqlx::Error> for BlobError {
    fn from(e: sqlx::Error) -> Self {
        BlobError::Sqlx(e)
    }
}

impl From<BlobError> for Error {
    fn from(e: BlobError) -> Self {
        match e {
            BlobError::Unauthorized => error::ErrorUnauthorized("unauthorized access"),
            BlobError::InvalidHash => error::ErrorBadRequest("invalid hash"),
            BlobError::StoreError => error::ErrorInternalServerError("could not retrieve blob"),
            BlobError::Sqlx(_) => error::ErrorInternalServerError("could not retrieve blob"),
        }
    }
}
