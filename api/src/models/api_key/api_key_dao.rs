use super::ApiKeyError;
use crate::state::AppStateRaw;

/// The data required to insert a new hashed API key into the database.
///
// Note: Originally, the idea was to stored a bcrypt hashed version of the API key, rather than the
// plaintext, in the same way as one would always avoid hash passwords provided by users. However,
// this actually isn't really necessary for API keys, because they are randomly generated strings
// which can't be guessed and are unlikely to be reused by end users on other services. See:
// https://security.stackexchange.com/questions/38566/how-is-storing-an-api-secret-key-in-plaintext-in-a-database-secure
// for a detailed discussion. The tradeoff is favourable, because hashing the API key on every
// request to verify it matches the stored hash is expensive (bcrypt deliberately introduces a cost).
// Instead, we use API keys more like session tokens, as described in the link.
#[derive(Serialize, Debug)]
pub struct InsertKey<'a> {
    pub email: String,
    pub label: String,
    pub key: &'a String,
}

#[async_trait]
pub trait IApiKey: std::ops::Deref<Target = AppStateRaw> {
    async fn insert_key(&self, insert_key: &InsertKey) -> Result<(), ApiKeyError> {
        let res = query!(
            r#"INSERT INTO api_keys AS a (user_id, label, key) 
           SELECT id, $2, $3 
           FROM users 
           WHERE email = $1
           "#,
            insert_key.email,
            insert_key.label,
            insert_key.key,
        )
        .execute(&self.db_conn)
        .await?;

        if res.rows_affected() == 0 {
            Err(ApiKeyError::InvalidEmail)
        } else {
            Ok(())
        }
    }
}

impl IApiKey for &AppStateRaw {}
