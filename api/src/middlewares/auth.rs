use crate::handlers::login::Claims;
use crate::CONFIG;

use actix_web::{dev, error, FromRequest, HttpRequest};
use futures::future::{err, ok, Ready};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};

#[derive(Debug)]
pub enum Auth {
    /// API-key based auth. This string is not validated until SQL queries use it.
    ApiKey(String),
    /// JWT based auth. If a JWT is provided, it is immediately decoded and checked
    /// for validity. If this process succeeds, the claims are stored here.
    Jwt(Claims),
}

#[derive(Debug)]
pub enum AuthError {
    NoAuthHeader,
    InvalidAuthHeader(String),
    InvalidJwt(jsonwebtoken::errors::Error),
}

impl From<AuthError> for actix_web::Error {
    fn from(e: AuthError) -> Self {
        match e {
            AuthError::NoAuthHeader => {
                error::ErrorUnauthorized("Error: No `Authorization` header present on request.")
            }
            AuthError::InvalidAuthHeader(s) => {
                error::ErrorUnauthorized(format!("Error: Invalid `Authorization` header. {}", s))
            }
            AuthError::InvalidJwt(_) => error::ErrorForbidden("Error: Invalid JWT provided."),
        }
    }
}

impl Auth {
    fn from_str(s: &str) -> Result<Self, AuthError> {
        if s.starts_with(&"Bearer ") {
            // The token is a JWT.
            Auth::from_jwt(s)
        } else {
            // The token is an API key.
            Auth::from_api_key(s)
        }
    }

    // Assumes that the string begins with "Bearer " (i.e. including the space).
    fn from_jwt(s: &str) -> Result<Self, AuthError> {
        let token = s
            .split("Bearer")
            .collect::<Vec<&str>>()
            .get(1)
            .map(|w| w.trim())
            .ok_or(AuthError::InvalidAuthHeader(
                "Header should be of the form `Bearer {token}`".to_string(),
            ))?;

        let key = &*CONFIG.jwt_priv.as_bytes();
        match decode::<Claims>(
            token,
            &DecodingKey::from_secret(key),
            &Validation::new(Algorithm::HS256),
        ) {
            Ok(data) => Ok(Auth::Jwt(data.claims)),
            Err(e) => Err(AuthError::InvalidJwt(e)),
        }
    }

    fn from_api_key(s: &str) -> Result<Self, AuthError> {
        Ok(Auth::ApiKey(s.to_string()))
    }

    pub fn is_jwt(&self) -> bool {
        match self {
            Auth::ApiKey(_) => false,
            Auth::Jwt(_) => true,
        }
    }
    pub fn is_api_key(&self) -> bool {
        match self {
            Auth::ApiKey(_) => true,
            Auth::Jwt(_) => false,
        }
    }

    /// Returns the inner API key. Returns `None` if this instance is a JWT.
    pub fn api_key(&self) -> Option<&str> {
        match self {
            Auth::ApiKey(s) => Some(s),
            Auth::Jwt(_) => None,
        }
    }

    /// Returns the inner JWT. Returns `None` if this instance is an API key.
    pub fn jwt(&self) -> Option<&Claims> {
        match self {
            Auth::ApiKey(_) => None,
            Auth::Jwt(c) => Some(&c),
        }
    }

    /// Call this on the `Auth` extracted from a request if you wish to accept only the JWT
    /// authentication strategy. In the error case, this function returns an
    /// `actix_web::Error`, so the result can be early returned from the handler with `?`.
    pub fn allow_only_jwt(&self) -> Result<&Claims, actix_web::Error> {
        match self {
            Auth::Jwt(c) => Ok(c),
            Auth::ApiKey(_) => Err(error::ErrorForbidden(
                "Invalid `Authorization` header. Expected JWT.",
            )),
        }
    }

    /// Call this on the `Auth` extracted from a request if you wish to accept only the API key
    /// authentication strategy. In the error case, this function returns an
    /// `actix_web::Error`, so the result can be early returned from the handler with `?`.
    pub fn allow_only_api_key(&self) -> Result<&str, actix_web::Error> {
        match self {
            Auth::Jwt(_) => Err(error::ErrorForbidden(
                "Invalid `Authorization` header. Expected API key.",
            )),
            Auth::ApiKey(k) => Ok(k),
        }
    }
}

impl FromRequest for Auth {
    type Error = AuthError;
    type Future = Ready<Result<Auth, Self::Error>>;

    fn from_request(req: &HttpRequest, _payload: &mut dev::Payload) -> Self::Future {
        let token = req
            .headers()
            .get("Authorization")
            .and_then(|h| h.to_str().ok())
            .ok_or(AuthError::NoAuthHeader);

        match token {
            Ok(token) => {
                let auth = Auth::from_str(token);
                match auth {
                    Ok(auth) => ok(auth),
                    Err(e) => err(e),
                }
            }
            Err(e) => err(e),
        }
    }
}
