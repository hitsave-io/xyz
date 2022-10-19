use actix_web::{error, FromRequest, HttpRequest};
use futures::future::{err, ok, Ready};

/// `AuthService` simply extracts the API key from the `Authorization` header in HTTP requests and
/// makes it accessible to handlers. We should _not_ make any kind of DB round-trip here.
/// Authorization should occur inside the single SQL query we make for accessing the resource being
/// requested.
#[derive(Clone, Debug)]
pub struct Auth {
    pub key: String,
}

impl Auth {
    fn from_str(key: &str) -> Self {
        Self {
            key: key.to_string(),
        }
    }
}

impl FromRequest for Auth {
    type Error = error::Error;
    type Future = Ready<Result<Auth, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut actix_web::dev::Payload) -> Self::Future {
        let api_auth_service = req
            .headers()
            .get("Authorization")
            .and_then(|h| h.to_str().ok())
            .and_then(|k| Some(Auth::from_str(k)));

        match api_auth_service {
            Some(a) => ok(a),
            None => err(error::ErrorUnauthorized("no Authorization header present")),
        }
    }
}
