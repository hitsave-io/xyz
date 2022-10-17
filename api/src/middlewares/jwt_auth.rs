use actix_web::{dev, error, FromRequest, HttpRequest};
use futures::future::{err, ok, Ready};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use std::borrow::Cow;

use crate::handlers::login::Claims;
use crate::CONFIG;

#[derive(Debug)]
pub struct AuthorizationService {
    pub claims: Claims,
}

#[derive(Debug)]
pub enum AuthError {
    NoAuthHeader,
    InvalidToken(jsonwebtoken::errors::Error),
}

impl From<AuthError> for actix_web::Error {
    fn from(e: AuthError) -> Self {
        match e {
            AuthError::NoAuthHeader => {
                log::error!("unauthorized request; no auth header {:?}", e);
                error::ErrorUnauthorized("no Authorization header included in request")
            }
            AuthError::InvalidToken(e) => {
                log::error!("unauthorized request; invalid JWT: {:?}", e);
                error::ErrorUnauthorized("no Authorization header included in request")
            }
        }
    }
}

impl AuthorizationService {}

impl FromRequest for AuthorizationService {
    type Error = AuthError;
    type Future = Ready<Result<AuthorizationService, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut dev::Payload) -> Self::Future {
        let token = req
            .headers()
            .get("Authorization")
            .and_then(|h| h.to_str().ok())
            .and_then(|h| {
                let words = h.split("Bearer").collect::<Vec<&str>>();
                let token = words.get(1).map(|w| w.trim());
                token.map(|t| Cow::Borrowed(t))
            });

        let token = token.as_ref().ok_or_else(|| AuthError::NoAuthHeader);

        match token {
            Ok(tok) => {
                let key = &*CONFIG.jwt_priv.as_bytes();
                match decode::<Claims>(
                    tok,
                    &DecodingKey::from_secret(key),
                    &Validation::new(Algorithm::HS256),
                ) {
                    Ok(token_data) => ok::<AuthorizationService, AuthError>(AuthorizationService {
                        claims: token_data.claims,
                    }),
                    Err(e) => err::<AuthorizationService, AuthError>(AuthError::InvalidToken(e)),
                }
            }
            Err(e) => err(e),
        }
    }
}
