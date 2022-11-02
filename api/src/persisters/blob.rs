use crate::handlers::blob::{BlobParams, BlobParamsHead};
use crate::middlewares::auth::Auth;
use crate::persisters::s3store::BlobMetadata;
use crate::persisters::{s3store::StoreError, Persist, Query};
use crate::state::State;
use actix_web::{
    body::BodyStream, error, http::StatusCode, web::Path, Error, HttpResponse, HttpResponseBuilder,
};
use blake3::{Hash, HexError};

#[derive(Deserialize, Debug)]
pub struct BlobInsert {
    pub content_length: i64,
    pub content_hash: String,
}

impl BlobMetadata for BlobInsert {
    fn content_length(&self) -> i64 {
        self.content_length
    }

    fn content_hash(&self) -> &str {
        &self.content_hash
    }
}

struct BlobInsertResult {
    id: Option<i64>,
}

#[async_trait]
impl Persist for BlobInsert {
    type Ret = i64;
    type Error = BlobError;

    async fn persist(self, auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error> {
        let api_key = auth
            .ok_or(BlobError::Unauthorized)?
            .api_key()
            .ok_or(BlobError::Unauthorized)?;

        // Insert blob.
        let blob_res = query_as!(
            BlobInsertResult,
            r#"
            WITH s AS (
                SELECT id 
                FROM blobs 
                WHERE user_id = user_from_key($1) 
                AND content_hash = $2
            ), i AS (
                INSERT INTO blobs (user_id, content_hash)
                VALUES (user_from_key($1), $2)
                ON CONFLICT DO NOTHING
                RETURNING id
            )
            SELECT id
            FROM i UNION ALL
            SELECT id
            FROM s
            "#,
            api_key,
            self.content_hash,
        )
        .fetch_one(&state.db_conn)
        .await?;

        // TODO: get rid of the expect
        Ok(blob_res.id.expect("should always be some"))
    }
}

#[async_trait]
impl Query for Path<BlobParams> {
    type Resolve = HttpResponse;
    type Error = BlobError;

    async fn fetch(self, auth: Option<&Auth>, state: &State) -> Result<Self::Resolve, Self::Error> {
        let api_key = auth
            .ok_or(BlobError::Unauthorized)?
            .api_key()
            .ok_or(BlobError::Unauthorized)?;

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
            api_key
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

#[async_trait]
impl Query for Path<BlobParamsHead> {
    type Resolve = ();
    type Error = BlobError;

    async fn fetch(self, auth: Option<&Auth>, state: &State) -> Result<Self::Resolve, Self::Error> {
        let api_key = auth
            .ok_or(BlobError::Unauthorized)?
            .api_key()
            .ok_or(BlobError::Unauthorized)?;

        let content_hash = self.into_inner().content_hash;

        // 1. Check the hash is valid.
        let _hash = Hash::from_hex(&content_hash)?;

        // 2. Check postgres to make sure they are authed.
        let res = query!(
            r#"
                SELECT count(id) FROM blobs
                WHERE   content_hash = $1
                    AND user_id = user_from_key($2)
           "#,
            content_hash,
            api_key
        )
        .fetch_one(&state.db_conn)
        .await?;

        if res.count != Some(1) {
            return Err(BlobError::NotFound);
        }

        Ok(())
    }
}

pub enum BlobError {
    Unauthorized,
    NotFound,
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

impl From<BlobError> for StoreError {
    // TODO: this is way too hacky....
    fn from(e: BlobError) -> Self {
        match e {
            BlobError::Unauthorized => StoreError::Unauthorized,
            BlobError::InvalidHash => StoreError::InvalidHash,
            BlobError::NotFound => StoreError::NotFound,
            // ...especially this!
            BlobError::StoreError => StoreError::Unauthorized,
            BlobError::Sqlx(e) => StoreError::Sqlx(e),
        }
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
            BlobError::NotFound => error::ErrorNotFound("resource not found"),
            BlobError::StoreError => error::ErrorInternalServerError("could not retrieve blob"),
            BlobError::Sqlx(_) => error::ErrorInternalServerError("could not retrieve blob"),
        }
    }
}
