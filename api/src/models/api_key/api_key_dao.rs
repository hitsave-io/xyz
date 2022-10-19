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
    pub user_id: sqlx::types::Uuid,
    pub label: String,
    pub key: &'a String,
}

struct ReturnedInsert {
    key: String,
    user_id: sqlx::types::Uuid,
}

#[async_trait]
pub trait IApiKey: std::ops::Deref<Target = AppStateRaw> {
    async fn insert_key(&self, insert_key: &InsertKey) -> Result<(), ApiKeyError> {
        let res = query_as!(
            ReturnedInsert,
            r#"INSERT INTO api_keys AS a (user_id, label, key) VALUES ($1, $2, $3) 
            RETURNING key, user_id"#,
            insert_key.user_id,
            insert_key.label,
            insert_key.key,
        )
        .fetch_one(&self.db_conn)
        .await;

        match res {
            Ok(r) => {
                log::debug!(
                    "inserted API key: user_id: {:?}, key: {:?}",
                    r.user_id,
                    format!("...{}", &r.key[r.key.len() - 5..])
                );
                Ok(())
            }
            Err(err) => match err {
                sqlx::Error::Database(ref e) => {
                    if e.code() == Some(std::borrow::Cow::Borrowed("23503")) {
                        Err(ApiKeyError::Unauthorized)
                    } else {
                        Err(ApiKeyError::Sqlx(err))
                    }
                }
                _ => Err(ApiKeyError::Sqlx(err)),
            },
        }
    }
}

impl IApiKey for &AppStateRaw {}
