use std::{
    fmt,
    future::Future,
    marker::PhantomData,
    ops,
    pin::Pin,
    sync::Arc,
    task::{Context, Poll},
};

use bytes::BytesMut;
use futures_core::{ready, Stream as _};
use serde::{de::DeserializeOwned, Serialize};

use derive_more::{Display, Error};

use actix_http::Payload;

use actix_web::dev::Decompress;
use actix_web::{
    body::EitherBody,
    error::{Error, PayloadError, ResponseError},
    http::{header::CONTENT_LENGTH, StatusCode},
    web, FromRequest, HttpMessage, HttpRequest, HttpResponse, Responder,
};

/// MessagePack extractor and responder.
///
/// `MsgPack` has two uses: MessagePack responses, and extracting typed data from MessagePack request payloads.
///
/// # Extractor
/// To extract typed data from a request body, the inner type `T` must implement the
/// [`serde::Deserialize`] trait.
///
/// Use [`MsgPackConfig`] to configure extraction options.
///
/// ```
/// use actix_web::{post, web, App};
/// use serde::Deserialize;
///
/// #[derive(Deserialize)]
/// struct Info {
///     username: String,
/// }
///
/// /// deserialize `Info` from request's body
/// #[post("/")]
/// async fn index(info: MsgPack<Info>) -> String {
///     format!("Welcome {}!", info.username)
/// }
/// ```
///
/// # Responder
/// The `MsgPack` type  MessagePack formatted responses. A handler may return a value of type
/// `MsgPack<T>` where `T` is the type of a structure to serialize into MessagePack. The type `T` must
/// implement [`serde::Serialize`].
///
/// ```
/// use actix_web::{post, web, HttpRequest};
/// use serde::Serialize;
///
/// #[derive(Serialize)]
/// struct Info {
///     name: String,
/// }
///
/// #[post("/{name}")]
/// async fn index(req: HttpRequest) -> MsgPack<Info> {
///     MsgPack(Info {
///         name: req.match_info().get("name").unwrap().to_owned(),
///     })
/// }
/// ```
#[derive(Debug)]
pub struct MsgPack<T>(pub T);

impl<T> MsgPack<T> {
    /// Unwrap into inner `T` value.
    pub fn into_inner(self) -> T {
        self.0
    }
}

impl<T> ops::Deref for MsgPack<T> {
    type Target = T;

    fn deref(&self) -> &T {
        &self.0
    }
}

impl<T> ops::DerefMut for MsgPack<T> {
    fn deref_mut(&mut self) -> &mut T {
        &mut self.0
    }
}

impl<T: fmt::Display> fmt::Display for MsgPack<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(&self.0, f)
    }
}

impl<T: Serialize> Serialize for MsgPack<T> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        self.0.serialize(serializer)
    }
}

/// Creates response with OK status code, correct content type header, and serialized MessagePack payload.
///
/// If serialization failed
impl<T: Serialize> Responder for MsgPack<T> {
    type Body = EitherBody<Vec<u8>>;

    fn respond_to(self, _: &HttpRequest) -> HttpResponse<Self::Body> {
        let mut buf = Vec::new();
        let res = self
            .0
            .serialize(&mut rmp_serde::Serializer::new(&mut buf).with_struct_map());

        match res {
            Ok(()) => match HttpResponse::Ok()
                .content_type("application/x-msgpack")
                .message_body(buf)
            {
                Ok(res) => res.map_into_left_body(),
                Err(err) => HttpResponse::from_error(err).map_into_right_body(),
            },

            Err(err) => {
                HttpResponse::from_error(MsgPackPayloadError::Serialize(err)).map_into_right_body()
            }
        }
    }
}

/// See [here](#extractor) for example of usage as an extractor.
impl<T: DeserializeOwned> FromRequest for MsgPack<T> {
    type Error = Error;
    type Future = MsgPackExtractFut<T>;

    #[inline]
    fn from_request(req: &HttpRequest, payload: &mut Payload) -> Self::Future {
        let config = MsgPackConfig::from_req(req);

        let limit = config.limit;
        let ctype_required = config.content_type_required;
        let err_handler = config.err_handler.clone();

        MsgPackExtractFut {
            req: Some(req.clone()),
            fut: MsgPackBody::new(req, payload, ctype_required).limit(limit),
            err_handler,
        }
    }
}

type MsgPackErrorHandler =
    Option<Arc<dyn Fn(MsgPackPayloadError, &HttpRequest) -> Error + Send + Sync>>;

pub struct MsgPackExtractFut<T> {
    req: Option<HttpRequest>,
    fut: MsgPackBody<T>,
    err_handler: MsgPackErrorHandler,
}

impl<T: DeserializeOwned> Future for MsgPackExtractFut<T> {
    type Output = Result<MsgPack<T>, Error>;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        let this = self.get_mut();

        let res = ready!(Pin::new(&mut this.fut).poll(cx));

        let res = match res {
            Err(err) => {
                let req = this.req.take().unwrap();
                log::debug!(
                    "Failed to deserialize MsgPack from payload. \
                         Request path: {}",
                    req.path()
                );

                if let Some(err_handler) = this.err_handler.as_ref() {
                    Err((*err_handler)(err, &req))
                } else {
                    Err(err.into())
                }
            }
            Ok(data) => Ok(MsgPack(data)),
        };

        Poll::Ready(res)
    }
}

/// `MsgPack` extractor configuration.
///
/// # Examples
/// ```
/// use actix_web::{error, post, web, App, FromRequest, HttpResponse};
/// use serde::Deserialize;
///
/// #[derive(Deserialize)]
/// struct Info {
///     name: String,
/// }
///
/// // `MsgPack` extraction is bound by custom `MsgPackConfig` applied to App.
/// #[post("/")]
/// async fn index(info: MsgPack<Info>) -> String {
///     format!("Welcome {}!", info.name)
/// }
///
/// // custom `MessagePack` extractor configuration
/// let msgpack_cfg = MsgPackConfig::default()
///     // limit request payload size
///     .limit(4096)
///     // only accept text/plain content type
///     .content_type(|mime| mime == mime::TEXT_PLAIN)
///     // use custom error handler
///     .error_handler(|err, req| {
///         error::InternalError::from_response(err, HttpResponse::Conflict().into()).into()
///     });
///
/// App::new()
///     .app_data(msgpack_cfg)
///     .service(index);
/// ```
#[derive(Clone)]
pub struct MsgPackConfig {
    limit: usize,
    err_handler: MsgPackErrorHandler,
    content_type: Option<Arc<dyn Fn(mime::Mime) -> bool + Send + Sync>>,
    content_type_required: bool,
}

impl MsgPackConfig {
    /// Set maximum accepted payload size. By default this limit is 2MB.
    pub fn limit(mut self, limit: usize) -> Self {
        self.limit = limit;
        self
    }

    /// Set custom error handler.
    pub fn error_handler<F>(mut self, f: F) -> Self
    where
        F: Fn(MsgPackPayloadError, &HttpRequest) -> Error + Send + Sync + 'static,
    {
        self.err_handler = Some(Arc::new(f));
        self
    }

    /// Set predicate for allowed content types.
    pub fn content_type<F>(mut self, predicate: F) -> Self
    where
        F: Fn(mime::Mime) -> bool + Send + Sync + 'static,
    {
        self.content_type = Some(Arc::new(predicate));
        self
    }

    /// Sets whether or not the request must have a `Content-Type` header to be parsed.
    pub fn content_type_required(mut self, content_type_required: bool) -> Self {
        self.content_type_required = content_type_required;
        self
    }

    /// Extract payload config from app data. Check both `T` and `Data<T>`, in that order, and fall
    /// back to the default payload config.
    fn from_req(req: &HttpRequest) -> &Self {
        req.app_data::<Self>()
            .or_else(|| req.app_data::<web::Data<Self>>().map(|d| d.as_ref()))
            .unwrap_or(&DEFAULT_CONFIG)
    }
}

const DEFAULT_LIMIT: usize = 2_097_152; // 2MB

/// Allow shared refs used as default.
const DEFAULT_CONFIG: MsgPackConfig = MsgPackConfig {
    limit: DEFAULT_LIMIT,
    err_handler: None,
    content_type: None,
    content_type_required: true,
};

impl Default for MsgPackConfig {
    fn default() -> Self {
        DEFAULT_CONFIG.clone()
    }
}

/// Future that resolves to some `T` when parsed from a MsgPack payload.
///
/// Can deserialize any type `T` that implements [`Deserialize`][serde::Deserialize].
///
/// Returns error if:
/// - `Content-Type` is not `application/x-msgpack` when `ctype_required` (passed to [`new`][Self::new])
///   is `true`.
/// - `Content-Length` is greater than [limit](MsgPackBody::limit()).
/// - The payload, when consumed, is not valid MessagePack.
pub enum MsgPackBody<T> {
    Error(Option<MsgPackPayloadError>),
    Body {
        limit: usize,
        /// Length as reported by `Content-Length` header, if present.
        length: Option<usize>,
        payload: Decompress<Payload>,
        buf: BytesMut,
        _res: PhantomData<T>,
    },
}

impl<T> Unpin for MsgPackBody<T> {}

impl<T: DeserializeOwned> MsgPackBody<T> {
    /// Create a new future to decode a MsgPack request payload.
    #[allow(clippy::borrow_interior_mutable_const)]
    pub fn new(req: &HttpRequest, payload: &mut Payload, ctype_required: bool) -> Self {
        // check content-type
        let can_parse_msgpack = if req.content_type() == "application/x-msgpack" {
            true
        } else {
            // if `ctype_required` is false, assume payload is
            // MessagePack even when content-type header is missing
            !ctype_required
        };

        if !can_parse_msgpack {
            return MsgPackBody::Error(Some(MsgPackPayloadError::ContentType));
        }

        let length = req
            .headers()
            .get(&CONTENT_LENGTH)
            .and_then(|l| l.to_str().ok())
            .and_then(|s| s.parse::<usize>().ok());

        // Notice the content-length is not checked against limit of config here.
        // As the internal usage always call MsgPackBody::limit after MsgPackBody::new.
        // And limit check to return an error variant of MsgPackBody happens there.

        let payload = Decompress::from_headers(payload.take(), req.headers());

        MsgPackBody::Body {
            limit: DEFAULT_LIMIT,
            length,
            payload,
            buf: BytesMut::with_capacity(8192),
            _res: PhantomData,
        }
    }

    /// Set maximum accepted payload size. The default limit is 2MB.
    pub fn limit(self, limit: usize) -> Self {
        match self {
            MsgPackBody::Body {
                length,
                payload,
                buf,
                ..
            } => {
                if let Some(len) = length {
                    if len > limit {
                        return MsgPackBody::Error(Some(
                            MsgPackPayloadError::OverflowKnownLength { length: len, limit },
                        ));
                    }
                }

                MsgPackBody::Body {
                    limit,
                    length,
                    payload,
                    buf,
                    _res: PhantomData,
                }
            }
            MsgPackBody::Error(e) => MsgPackBody::Error(e),
        }
    }
}

impl<T: DeserializeOwned> Future for MsgPackBody<T> {
    type Output = Result<T, MsgPackPayloadError>;

    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        let this = self.get_mut();

        match this {
            MsgPackBody::Body {
                limit,
                buf,
                payload,
                ..
            } => loop {
                let res = ready!(Pin::new(&mut *payload).poll_next(cx));
                match res {
                    Some(chunk) => {
                        let chunk = chunk?;
                        let buf_len = buf.len() + chunk.len();
                        if buf_len > *limit {
                            return Poll::Ready(Err(MsgPackPayloadError::Overflow {
                                limit: *limit,
                            }));
                        } else {
                            buf.extend_from_slice(&chunk);
                        }
                    }
                    None => {
                        let msgpack = rmp_serde::from_slice::<T>(buf)
                            .map_err(MsgPackPayloadError::Deserialize)?;
                        return Poll::Ready(Ok(msgpack));
                    }
                }
            },
            MsgPackBody::Error(e) => Poll::Ready(Err(e.take().unwrap())),
        }
    }
}

/// A set of errors that can occur during parsing MessagePack payloads
#[derive(Debug, Display, Error)]
#[non_exhaustive]
pub enum MsgPackPayloadError {
    /// Payload size is bigger than allowed & content length header set. (default: 2MB)
    #[display(
        fmt = "MessagePack payload ({} bytes) is larger than allowed (limit: {} bytes).",
        length,
        limit
    )]
    OverflowKnownLength { length: usize, limit: usize },

    /// Payload size is bigger than allowed but no content length header set. (default: 2MB)
    #[display(fmt = "MessagePack payload has exceeded limit ({} bytes).", limit)]
    Overflow { limit: usize },

    /// Content type error
    #[display(fmt = "Content type error")]
    ContentType,

    /// Deserialize error
    #[display(fmt = "MessagePack deserialize error: {}", _0)]
    Deserialize(rmp_serde::decode::Error),

    /// Serialize error
    #[display(fmt = "MessagePack serialize error: {}", _0)]
    Serialize(rmp_serde::encode::Error),

    /// Payload error
    #[display(fmt = "Error that occur during reading payload: {}", _0)]
    Payload(PayloadError),
}

impl From<PayloadError> for MsgPackPayloadError {
    fn from(err: PayloadError) -> Self {
        Self::Payload(err)
    }
}

impl ResponseError for MsgPackPayloadError {
    fn status_code(&self) -> StatusCode {
        match self {
            Self::OverflowKnownLength {
                length: _,
                limit: _,
            } => StatusCode::PAYLOAD_TOO_LARGE,
            Self::Overflow { limit: _ } => StatusCode::PAYLOAD_TOO_LARGE,
            Self::Serialize(_) => StatusCode::INTERNAL_SERVER_ERROR,
            Self::Payload(err) => err.status_code(),
            _ => StatusCode::BAD_REQUEST,
        }
    }
}

// #[cfg(test)]
// mod tests {
//     use bytes::Bytes;
//     use serde::{Deserialize, Serialize};
//
//     use super::*;
//     use crate::{
//         body,
//         error::InternalError,
//         http::{
//             header::{self, CONTENT_LENGTH, CONTENT_TYPE},
//             StatusCode,
//         },
//         test::{assert_body_eq, TestRequest},
//     };
//
//     #[derive(Serialize, Deserialize, PartialEq, Debug)]
//     struct MyObject {
//         name: String,
//     }
//
//     fn json_eq(err: JsonPayloadError, other: JsonPayloadError) -> bool {
//         match err {
//             JsonPayloadError::Overflow { .. } => {
//                 matches!(other, JsonPayloadError::Overflow { .. })
//             }
//             JsonPayloadError::OverflowKnownLength { .. } => {
//                 matches!(other, JsonPayloadError::OverflowKnownLength { .. })
//             }
//             JsonPayloadError::ContentType => matches!(other, JsonPayloadError::ContentType),
//             _ => false,
//         }
//     }
//
//     #[actix_rt::test]
//     async fn test_responder() {
//         let req = TestRequest::default().to_http_request();
//
//         let j = Json(MyObject {
//             name: "test".to_string(),
//         });
//         let res = j.respond_to(&req);
//         assert_eq!(res.status(), StatusCode::OK);
//         assert_eq!(
//             res.headers().get(header::CONTENT_TYPE).unwrap(),
//             header::HeaderValue::from_static("application/json")
//         );
//         assert_body_eq!(res, b"{\"name\":\"test\"}");
//     }
//
//     #[actix_rt::test]
//     async fn test_custom_error_responder() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(JsonConfig::default().limit(10).error_handler(|err, _| {
//                 let msg = MyObject {
//                     name: "invalid request".to_string(),
//                 };
//                 let resp =
//                     HttpResponse::BadRequest().body(serde_json::to_string(&msg).unwrap());
//                 InternalError::from_response(err, resp).into()
//             }))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         let resp = HttpResponse::from_error(s.unwrap_err());
//         assert_eq!(resp.status(), StatusCode::BAD_REQUEST);
//
//         let body = body::to_bytes(resp.into_body()).await.unwrap();
//         let msg: MyObject = serde_json::from_slice(&body).unwrap();
//         assert_eq!(msg.name, "invalid request");
//     }
//
//     #[actix_rt::test]
//     async fn test_extract() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await.unwrap();
//         assert_eq!(s.name, "test");
//         assert_eq!(
//             s.into_inner(),
//             MyObject {
//                 name: "test".to_string()
//             }
//         );
//
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(JsonConfig::default().limit(10))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(format!("{}", s.err().unwrap())
//             .contains("JSON payload (16 bytes) is larger than allowed (limit: 10 bytes)."));
//
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(
//                 JsonConfig::default()
//                     .limit(10)
//                     .error_handler(|_, _| JsonPayloadError::ContentType.into()),
//             )
//             .to_http_parts();
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(format!("{}", s.err().unwrap()).contains("Content type error"));
//     }
//
//     #[actix_rt::test]
//     async fn test_json_body() {
//         let (req, mut pl) = TestRequest::default().to_http_parts();
//         let json = JsonBody::<MyObject>::new(&req, &mut pl, None, true).await;
//         assert!(json_eq(json.err().unwrap(), JsonPayloadError::ContentType));
//
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/text"),
//             ))
//             .to_http_parts();
//         let json = JsonBody::<MyObject>::new(&req, &mut pl, None, true).await;
//         assert!(json_eq(json.err().unwrap(), JsonPayloadError::ContentType));
//
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("10000"),
//             ))
//             .to_http_parts();
//
//         let json = JsonBody::<MyObject>::new(&req, &mut pl, None, true)
//             .limit(100)
//             .await;
//         assert!(json_eq(
//             json.err().unwrap(),
//             JsonPayloadError::OverflowKnownLength {
//                 length: 10000,
//                 limit: 100
//             }
//         ));
//
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .set_payload(Bytes::from_static(&[0u8; 1000]))
//             .to_http_parts();
//
//         let json = JsonBody::<MyObject>::new(&req, &mut pl, None, true)
//             .limit(100)
//             .await;
//
//         assert!(json_eq(
//             json.err().unwrap(),
//             JsonPayloadError::Overflow { limit: 100 }
//         ));
//
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("application/json"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .to_http_parts();
//
//         let json = JsonBody::<MyObject>::new(&req, &mut pl, None, true).await;
//         assert_eq!(
//             json.ok().unwrap(),
//             MyObject {
//                 name: "test".to_owned()
//             }
//         );
//     }
//
//     #[actix_rt::test]
//     async fn test_with_json_and_bad_content_type() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("text/plain"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(JsonConfig::default().limit(4096))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(s.is_err())
//     }
//
//     #[actix_rt::test]
//     async fn test_with_json_and_good_custom_content_type() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("text/plain"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(JsonConfig::default().content_type(|mime: mime::Mime| {
//                 mime.type_() == mime::TEXT && mime.subtype() == mime::PLAIN
//             }))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(s.is_ok())
//     }
//
//     #[actix_rt::test]
//     async fn test_with_json_and_bad_custom_content_type() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_TYPE,
//                 header::HeaderValue::from_static("text/html"),
//             ))
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(JsonConfig::default().content_type(|mime: mime::Mime| {
//                 mime.type_() == mime::TEXT && mime.subtype() == mime::PLAIN
//             }))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(s.is_err())
//     }
//
//     #[actix_rt::test]
//     async fn test_json_with_no_content_type() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((
//                 header::CONTENT_LENGTH,
//                 header::HeaderValue::from_static("16"),
//             ))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(JsonConfig::default().content_type_required(false))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(s.is_ok())
//     }
//
//     #[actix_rt::test]
//     async fn test_with_config_in_data_wrapper() {
//         let (req, mut pl) = TestRequest::default()
//             .insert_header((CONTENT_TYPE, mime::APPLICATION_JSON))
//             .insert_header((CONTENT_LENGTH, 16))
//             .set_payload(Bytes::from_static(b"{\"name\": \"test\"}"))
//             .app_data(web::Data::new(JsonConfig::default().limit(10)))
//             .to_http_parts();
//
//         let s = Json::<MyObject>::from_request(&req, &mut pl).await;
//         assert!(s.is_err());
//
//         let err_str = s.err().unwrap().to_string();
//         assert!(err_str
//             .contains("JSON payload (16 bytes) is larger than allowed (limit: 10 bytes)."));
//     }
// }
