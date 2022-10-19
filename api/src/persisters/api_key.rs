use crate::middlewares::api_auth::Auth;
use crate::models::api_key::ApiKeyError;
use crate::persisters::Persist;
use crate::state::State;

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
pub struct KeyInsert<'a> {
    pub user_id: sqlx::types::Uuid,
    pub label: String,
    pub key: &'a String,
}

struct KeyInsertResult {
    key: String,
    user_id: sqlx::types::Uuid,
}

#[async_trait]
impl Persist for KeyInsert<'_> {
    type Ret = ();
    type Error = ApiKeyError;

    async fn persist(self, _auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error> {
        let res = query_as!(
            KeyInsertResult,
            r#"INSERT INTO api_keys AS a (user_id, label, key) VALUES ($1, $2, $3)
            RETURNING key, user_id"#,
            self.user_id,
            self.label,
            self.key,
        )
        .fetch_one(&state.db_conn)
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
