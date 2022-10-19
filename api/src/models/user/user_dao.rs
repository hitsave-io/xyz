use crate::state::AppStateRaw;

use sqlx::{types::Uuid, Error};

#[derive(Debug)]
pub enum UserInsertError {
    AlreadyExists,
    /// This is used when the upsert query returns no rows. If the query is written correctly, this
    /// should never happen, because we either return the row that got inserted, or the one which
    /// is already there. In theory, this error is unreachable, but we want to handle it just in
    /// case, to avoid panics.
    UpsertError,
    Sqlx(sqlx::Error),
}

#[derive(Serialize, Deserialize, Debug)]
pub struct AddUser {
    pub gh_id: i32,
    pub gh_email: String,
    pub gh_login: String,
    pub gh_token: String,
    pub gh_avatar_url: String,
    pub email_verified: bool,
}

#[derive(Deserialize, Debug)]
pub struct UpsertResult {
    id: Option<Uuid>,
}

#[async_trait]
pub trait IUser: std::ops::Deref<Target = AppStateRaw> {
    async fn insert_user(&self, user: &AddUser) -> Result<Uuid, UserInsertError> {
        let res = query_as!(
            UpsertResult,
            // r#"INSERT INTO users 
            // (gh_id, gh_email, gh_login, gh_token, gh_avatar_url, email_verified) 
            // VALUES ($1, $2, $3, $4, $5, $6) RETURNING users.id"#,
            r#"WITH e AS(
                  INSERT INTO users (gh_id, gh_email, gh_login, gh_token, gh_avatar_url, email_verified) 
                         VALUES ($1, $2, $3, $4, $5, $6)
                  ON CONFLICT(gh_id) DO NOTHING
                  RETURNING id
               )
               SELECT id FROM e UNION
               SELECT id FROM users WHERE gh_id = $1;"#,
            user.gh_id,
            user.gh_email,
            user.gh_login,
            user.gh_token,
            user.gh_avatar_url,
            user.email_verified,
        )
        .fetch_one(&self.db_conn)
        .await
        .inspect_err(|e| error!("error inserting user: {:?}", e))?;

        let id = res.id.ok_or(UserInsertError::UpsertError)?;

        Ok(id)
    }
}

impl From<sqlx::Error> for UserInsertError {
    fn from(e: sqlx::Error) -> Self {
        match e {
            Error::Database(ref err) => {
                if err.code() == Some(std::borrow::Cow::Borrowed("23505")) {
                    Self::AlreadyExists
                } else {
                    Self::Sqlx(e)
                }
            }
            _ => Self::Sqlx(e),
        }
    }
}

impl IUser for &AppStateRaw {}
