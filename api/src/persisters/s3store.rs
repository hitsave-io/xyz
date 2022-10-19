use crate::extractors::with_blob::{BlobPayload, WithBlob, WithBlobError};
use crate::middlewares::api_auth::Auth;
use crate::models::eval::EvalError;
use crate::persisters::Persist;
use crate::state::State;

use aws_sdk_s3::{
    error::PutObjectError,
    output::PutObjectOutput,
    types::{ByteStream, SdkError},
    Client,
};
use blake3::{Hash, Hasher};
use futures::stream::StreamExt;

use std::marker::{Send, Sync};

/// This gets stored in application state and when we want to store something, we call `store`.
#[derive(Clone)]
pub struct S3Store {
    client: Client,
}

#[derive(Debug)]
pub enum StoreError {
    InvalidHash,
    MissingPayload,
    Unauthorized,
    S3(SdkError<PutObjectError>),
    WithBlob(WithBlobError),
    Sqlx(sqlx::error::Error),
}

impl From<EvalError> for StoreError {
    fn from(e: EvalError) -> Self {
        match e {
            EvalError::NotFound(e) => StoreError::Sqlx(e),
            EvalError::Sqlx(e) => StoreError::Sqlx(e),
            EvalError::Unauthorized => StoreError::Unauthorized,
        }
    }
}

impl std::fmt::Display for StoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            StoreError::InvalidHash => writeln!(f, "Invalid hash"),
            StoreError::MissingPayload => writeln!(f, "Missing payload"),
            StoreError::Unauthorized => writeln!(f, "Unauthorized"),
            StoreError::S3(_) => writeln!(f, "Error storing BLOB"),
            StoreError::WithBlob(_) => writeln!(f, "Error decoding BLOB transfer protocol"),
            StoreError::Sqlx(_) => writeln!(f, "Error storing BLOB metadata"),
        }
    }
}

impl std::error::Error for StoreError {}

impl From<sqlx::error::Error> for StoreError {
    fn from(e: sqlx::error::Error) -> Self {
        Self::Sqlx(e)
    }
}

impl From<StoreError> for actix_web::Error {
    fn from(e: StoreError) -> Self {
        use actix_web::error;
        match e {
            StoreError::S3(e) => {
                log::error!("error storing data in S3: {:?}", e);
                error::ErrorInternalServerError("could not store data in S3")
            }
            StoreError::Sqlx(e) => {
                log::error!("error storing byte metadata in Postgres: {:?}", e);
                error::ErrorInternalServerError("could not store data")
            }
            StoreError::InvalidHash => error::ErrorBadRequest("invalid hash"),
            StoreError::MissingPayload => error::ErrorBadRequest("missing payload"),
            StoreError::Unauthorized => error::ErrorUnauthorized("unauthorized"),
            StoreError::WithBlob(e) => {
                log::error!("error extracting BLOB from request: {:?}", e);
                error::ErrorBadRequest("invalid encoding")
            }
        }
    }
}

impl From<blake3::HexError> for StoreError {
    fn from(_: blake3::HexError) -> Self {
        Self::InvalidHash
    }
}

#[async_trait]
/// A trait implemented on types which allow storage of BLOBs in S3.
// TODO: We want to eventually implement different storage strategies based on the size of the
// bytes payload. Small payloads can be a single PUT with retries, large payloads can be
// split up with the multi part upload API, and probably with no retries.
pub trait BlobMetadata {
    /// The content hash to be used for addressing the underlying BLOB storage.
    fn content_hash(&self) -> &str;
    /// The length of the BLOB, in bytes.
    ///
    /// This is used as a hint when uploading the bytes to S3, since we may not have fully received
    /// the incoming byte stream when we start transmitting to S3. The S3 PUT operation may fail if
    /// the content length turns out to be different from what was originally returned by this
    /// method.
    fn content_length(&self) -> i64;
}

impl S3Store {
    pub async fn new() -> S3Store {
        let config = aws_config::from_env().region("eu-central-1").load().await;
        let client = Client::new(&config);

        Self { client }
    }

    /// Attempts to transmit the BLOB to S3.
    pub async fn store_blob(
        &self,
        payload: BlobPayload,
        hash_claim: Hash,
        content_length: i64,
    ) -> Result<PutObjectOutput, StoreError> {
        let stream = payload.scan((Hasher::new(), 0), move |(h, len), item| match item {
            Ok(ref b) => {
                h.update(&b);
                *len += b.len();

                if *len == content_length as usize {
                    let hash = h.finalize();
                    if hash != hash_claim {
                        return futures::future::ready(Some(Err(StoreError::InvalidHash)));
                    }
                }

                futures::future::ready(Some(Ok(b.clone())))
            }
            Err(e) => futures::future::ready(Some(Err(StoreError::WithBlob(e)))),
        });

        let body = hyper::Body::wrap_stream(stream);
        let byte_stream = ByteStream::new(body.into());

        // TODO: in the case that the hash doesn't match, the error returned from the final stream
        // item gets wrapped up in the AWS error types and it's difficult for us to get at it. For
        // now, we are correctly erroring but not returning a useful message to the user. It would
        // be better if we could inspect the AWS error and determine if it's the result of an
        // invalid hash. If so, this function should be returning `StoreError::InvalidHash` rather
        // than `StoreError::S3(err)`.
        let aws_res = self
            .client
            .put_object()
            .bucket("hitsave-binarystore")
            .key(hash_claim.to_hex().to_string())
            .body(byte_stream)
            .content_length(content_length)
            .send()
            .await
            .map_err(|e| StoreError::S3(e));

        aws_res
    }

    /// Attempts to retrieve the BLOB from S3.
    pub async fn retrieve_blob(&self, content_hash: Hash) -> Result<ByteStream, StoreError> {
        Ok(self
            .client
            .get_object()
            .bucket("hitsave-binarystore")
            .key(content_hash.to_hex().to_string())
            .send()
            .await
            .unwrap()
            .body)
    }
}

#[async_trait]
impl<P> Persist for WithBlob<P>
where
    P: Persist + BlobMetadata + Send + Sync + std::marker::Unpin,
    P::Error: Into<StoreError>,
{
    type Ret = <P as Persist>::Ret;
    type Error = StoreError;

    async fn persist(
        mut self,
        auth: Option<&Auth>,
        state: &State,
    ) -> Result<Self::Ret, Self::Error> {
        let payload = self.blob.take().ok_or(StoreError::MissingPayload)?;
        let meta = self.meta;

        let hash_hex = meta.content_hash();
        let hash = Hash::from_hex(hash_hex)?;

        let content_length = meta.content_length();

        // Attempt to store the byte stream in S3.
        let _s3_result = state
            .s3_store
            .store_blob(payload, hash, content_length)
            .await?;

        // If successful, move on to inserting the row in Postgres.
        meta.persist(auth, state).await.map_err(Into::into)
    }
}
