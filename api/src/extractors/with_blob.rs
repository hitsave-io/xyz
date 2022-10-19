use actix_web::{dev::Payload, error::PayloadError, FromRequest, HttpRequest, Result};
use futures_core::{ready, Stream};
use serde::de::DeserializeOwned;

use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};

/// Represents an attempt to transfer a BLOB via our encoding scheme. This type implements
/// `FromRequest`, so we can attempt to extract a `BlobTransfer` from any handler.
///
/// The type of the meta field is any type which implements `Deserialize`. This allows us to
/// abstract over any JSON header we anticipate.
///
/// Once we have a `BlobTransfer`, we won't have actually received the main BLOB payload, just the
/// header metadata. The `blob` field exposes the BLOB payload as a `BlobPaylaod` type, which
/// implements `Stream`.
pub struct WithBlob<M> {
    pub meta: M,
    pub blob: Option<BlobPayload>,
}

impl<M> WithBlob<M>
where
    M: DeserializeOwned,
{
    pub fn map<F, N>(self, f: F) -> WithBlob<N>
    where
        F: FnOnce(M) -> N,
    {
        let m = self.meta;
        let n = f(m);
        WithBlob {
            meta: n,
            blob: self.blob,
        }
    }
}

impl<M> std::fmt::Debug for WithBlob<M>
where
    M: std::fmt::Debug,
{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "WithBlob {{")?;
        writeln!(f, "  meta: {:?},", self.meta)?;
        writeln!(f, "  blob: --- PAYLOAD ---,")?;
        write!(f, "}}")
    }
}

pub struct BlobPayload {
    init_bytes: Option<Vec<u8>>,
    payload: Payload,
}

unsafe impl Send for BlobPayload {}
unsafe impl Sync for BlobPayload {}

impl BlobPayload {
    fn new(payload: Payload, init_bytes: &[u8]) -> Self {
        Self {
            init_bytes: Some(init_bytes.to_vec()),
            payload,
        }
    }
}

impl Stream for BlobPayload {
    type Item = Result<bytes::Bytes, WithBlobError>;

    fn poll_next(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        let this = self.get_mut();

        // First, we have to see whether we've yielded the initial bytes. If not, yield those, and
        // then move on to yielding from the underlying payload by delegation.
        if this.init_bytes.is_some() {
            return Poll::Ready(Some(Ok(this.init_bytes.take().expect("this works").into())));
        }

        Pin::new(&mut this.payload)
            .poll_next(cx)
            .map(|p| p.map(|r| r.map_err(|e| WithBlobError::Payload(e))))
    }
}

/// This future is responsible for accumulating the first 8 bytes of the payload, which are to be
/// interpreted as the length, in bytes, of the metadata block following.
pub struct BTExtractMetadataFut<M> {
    /// The `Payload` we are reading from actix.
    payload: Payload,
    /// The buffer we use to accumulate the size of the metadata JSON string in bytes. This is the
    /// first 8 bytes of the payload.
    size_buf: bytes::BytesMut,
    /// The size, in bytes, of the metadata. Before we have determined this value by reading the
    /// first 8 bytes of the `Payload`, this is `None`. We can rely on the `Some` vs. `None` of
    /// this value to know which phase of decoding we are in.
    metadata_len: Option<usize>,
    /// The amount of metadata we have actually received so far.
    metadata_received: usize,
    /// The buffer we use to accumulate the raw metadata bytes.
    metadata_buf: Vec<u8>,
    _phantom: std::marker::PhantomData<M>,
}

#[derive(Debug)]
pub enum WithBlobError {
    Payload(PayloadError),
    Deserialize(serde_json::Error),
    UnexpectedEOF,
}

impl std::fmt::Display for WithBlobError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WithBlobError::Payload(_) => writeln!(f, "Payload error"),
            WithBlobError::Deserialize(_) => writeln!(f, "Deserialize error"),
            WithBlobError::UnexpectedEOF => writeln!(f, "Unexpected EOF error"),
        }
    }
}

impl std::error::Error for WithBlobError {}

impl From<PayloadError> for WithBlobError {
    fn from(e: PayloadError) -> Self {
        Self::Payload(e)
    }
}

impl From<WithBlobError> for actix_web::Error {
    fn from(e: WithBlobError) -> Self {
        match e {
            WithBlobError::Payload(_) => {
                actix_web::error::ErrorInternalServerError("error receiving blob")
            }
            WithBlobError::UnexpectedEOF => {
                actix_web::error::ErrorBadRequest("unexpected end of byte stream")
            }
            WithBlobError::Deserialize(e) => actix_web::error::ErrorBadRequest(format!(
                "metadata deserialization error: {:?}",
                e
            )),
        }
    }
}

impl<M> Future for BTExtractMetadataFut<M>
where
    M: DeserializeOwned + std::marker::Unpin,
{
    type Output = Result<WithBlob<M>, WithBlobError>;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        // As we poll this, we will slowly accumulate all the metadata from the underlying
        // payload.
        //
        // We'll then build the `BlobTransfer` struct, and let the downstream consumer of that
        // extract the remaining bytes (ie. the BLOB).
        //
        // TODO: manually implement a maximum size for metadata buffers. Currently, since we can
        // have any integer representable in 4 bytes, the metadata can be 4GB. This is excessive.
        //
        // TODO: what happens if there's an empty payload? This needs to be a gracefully handled
        // error.
        let this = self.get_mut();
        let buf = &mut this.size_buf;

        loop {
            let res = ready!(Pin::new(&mut this.payload).poll_next(cx));

            match res {
                Some(chunk) => {
                    let chunk = chunk?;

                    if this.metadata_len == None {
                        // Here, we are still trying to determine the length of the metadata.
                        let buf_len = buf.len() + chunk.len();
                        if buf_len > 4 {
                            // Here we need to take just enough bytes to finish populating the sentinel
                            // length byte, and transfer the remaining bytes into the start of `metadata_buf`.
                            // After that, we need to deserialize the `size_buf` bytes, and set
                            // `metadata_len` to `Some(n)`.
                            buf.extend_from_slice(&chunk[..(buf_len - 4)]);
                            let sentinel: [u8; 4] = buf[..4].try_into().expect("this works");
                            let rem = &chunk[4..];
                            let metadata_len = u32::from_be_bytes(sentinel);
                            this.metadata_len = Some(metadata_len as usize);

                            this.metadata_buf
                                .try_reserve_exact(metadata_len as usize)
                                .expect("this will work , trust me");

                            if rem.len() > metadata_len as usize {
                                // It's possible that `rem` already contains more than the metadata and
                                // has already spilled into the underlying bytes. If this is the case,
                                // we are able to crack on and return the `BlobTransfer`.
                                let meta_buf = &rem[..(metadata_len as usize)];
                                let meta: M = serde_json::from_slice(&meta_buf)
                                    .map_err(|e| WithBlobError::Deserialize(e))?;
                                let first_blob_bytes = &rem[(metadata_len as usize)..];
                                let with_blob = WithBlob {
                                    meta,
                                    blob: Some(BlobPayload::new(
                                        this.payload.take(),
                                        first_blob_bytes,
                                    )),
                                };

                                return Poll::Ready(Ok(with_blob));
                            } else {
                                this.metadata_buf.extend_from_slice(rem);
                                this.metadata_received = rem.len().try_into()
                                .expect("this works; if the metadata was too long, we should have already errored earlier");
                            }
                        } else {
                            // Here we just extend the buffer with what we got and let the loop keep
                            // going.
                            buf.extend_from_slice(&chunk);
                        }
                    } else {
                        // Here, we are now accumulating data into the `metadata_buf` `Vec`.
                        // We need to keep checking for when we hit the end of the metadata by
                        // tracking how many bytes we've received. When we do hit the end, we need
                        // to handle excess bytes (i.e. the start of the BLOB payload), and then
                        // deserialize the metadata and construct the `BlobTransfer` object.
                        if this.metadata_received + chunk.len()
                            >= this.metadata_len.expect("this just has to work...")
                        {
                            // Here, we have just received a chunk containing the last of the
                            // metadata bytes. We need to handle the excess bytes, deserialize the
                            // JSON and construct the `BlobTransfer`.
                            let final_bytes_len = this.metadata_len.expect("this just has to work")
                                - this.metadata_received;
                            let final_bytes = &chunk[..final_bytes_len];
                            this.metadata_buf.extend_from_slice(&final_bytes);
                            this.metadata_received += final_bytes.len();

                            let first_blob_bytes = &chunk[final_bytes_len..];
                            let meta: M = serde_json::from_slice(&this.metadata_buf)
                                .map_err(|e| WithBlobError::Deserialize(e))?;

                            let with_blob = WithBlob {
                                meta,
                                blob: Some(BlobPayload::new(this.payload.take(), first_blob_bytes)),
                            };

                            return Poll::Ready(Ok(with_blob));
                        } else {
                            // Here, we just received more metadata, but there's more to come. Keep
                            // trucking.
                            this.metadata_buf.extend_from_slice(&chunk);
                        }
                    }
                }
                None => {
                    // If we get here, then something has gone wrong. We shouldn't have hit the end of
                    // the payload already. We shouldn't expect to reach that in processing this
                    // future. It is the consumer of the `BlobTransfer` who will get to EOF.
                    return Poll::Ready(Err(WithBlobError::UnexpectedEOF));
                }
            }
        }
    }
}

impl<M> FromRequest for WithBlob<M>
where
    M: DeserializeOwned + std::marker::Unpin,
{
    type Error = WithBlobError;
    type Future = BTExtractMetadataFut<M>;

    #[inline]
    fn from_request(_req: &HttpRequest, payload: &mut Payload) -> Self::Future {
        BTExtractMetadataFut {
            payload: payload.take(),
            // we know exactly how many bytes we need for this
            size_buf: bytes::BytesMut::with_capacity(4),
            // we can avoid an unnecesary allocation by calling `with_capacity(0)`. Once we know
            // the length to expect, we'll call `try_reserve_exact`, and set it to the precise
            // amount we need.
            metadata_buf: Vec::with_capacity(0),
            metadata_len: None,
            metadata_received: 0,
            _phantom: std::marker::PhantomData,
        }
    }
}
