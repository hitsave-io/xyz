use rand::distributions::Alphanumeric;
use rand::{Rng, SeedableRng};
use rand_chacha::ChaCha20Rng;

pub mod api_key_dao;
pub mod api_key_routes;

/// Represents the response to a key generation request, containing the API key only.
///
/// This is also used to represent the API key transmitted as auth by users accessing protected
/// routes.
#[derive(Serialize, Deserialize, Debug)]
pub struct ApiKey {
    pub key: String,
}

impl ApiKey {
    pub fn random() -> Self {
        // https://rust-lang-nursery.github.io/rust-cookbook/algorithms/randomness.html#create-random-passwords-from-a-set-of-alphanumeric-characters
        let key = ChaCha20Rng::from_entropy()
            .sample_iter(&Alphanumeric)
            .take(64)
            .map(char::from)
            .collect();

        Self { key }
    }
}

#[derive(Debug)]
pub enum ApiKeyError {
    /// Passes through sqlx errors.
    Sqlx(sqlx::Error),
    /// Represents scenario when a request is made to generate an API key for an email address not
    /// known to the database.
    InvalidEmail,
}

impl From<sqlx::Error> for ApiKeyError {
    fn from(err: sqlx::Error) -> Self {
        ApiKeyError::Sqlx(err)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generates_key() {
        assert_eq!(ApiKey::random().key.len(), 72);
    }
}
