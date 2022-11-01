use crate::middlewares::api_auth::Auth;
use crate::models::user::User;
use crate::persisters::{Persist, Query};
use crate::state::State;

use sqlx::{types::Uuid, Error};

#[derive(Debug)]
pub enum UserUpsertError {
    AlreadyExists,
    /// This is used when the upsert query returns no rows. If the query is written correctly, this
    /// should never happen, because we either return the row that got inserted, or the one which
    /// is already there. In theory, this error is unreachable, but we want to handle it just in
    /// case, to avoid panics.
    Unreachable,
    Sqlx(sqlx::Error),
}

#[derive(Serialize, Deserialize, Debug)]
pub struct UserUpsert {
    pub gh_id: i32,
    pub gh_email: String,
    pub gh_login: String,
    pub gh_token: String,
    pub gh_avatar_url: String,
    pub email_verified: bool,
}

pub struct UserGet {
    pub id: Uuid,
}

pub enum UserGetError {
    Sqlx(sqlx::Error),
}

impl From<sqlx::Error> for UserGetError {
    fn from(e: sqlx::Error) -> Self {
        Self::Sqlx(e)
    }
}

#[async_trait]
impl Query for UserGet {
    type Resolve = User;
    type Error = UserGetError;

    async fn fetch(
        self,
        _auth: Option<&Auth>,
        state: &State,
    ) -> Result<Self::Resolve, Self::Error> {
        let res = query_as!(
            User,
            r#"
            SELECT id, gh_id, gh_email, gh_login, gh_token, gh_avatar_url, email_verified 
            FROM users
            WHERE id = $1
            "#,
            &self.id,
        )
        .fetch_one(&state.db_conn)
        .await?;

        Ok(res)
    }
}

#[async_trait]
impl Persist for UserUpsert {
    type Ret = Uuid;
    type Error = UserUpsertError;

    async fn persist(self, _auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error> {
        let res = query_as!(
            UpsertResult,
            r#"WITH e AS(
                  INSERT INTO users (gh_id, gh_email, gh_login, gh_token, gh_avatar_url, email_verified) 
                         VALUES ($1, $2, $3, $4, $5, $6)
                  ON CONFLICT(gh_id) DO NOTHING
                  RETURNING id
               )
               SELECT id FROM e UNION
               SELECT id FROM users WHERE gh_id = $1;"#,
            &self.gh_id,
            &self.gh_email,
            &self.gh_login,
            &self.gh_token,
            &self.gh_avatar_url,
            &self.email_verified,
        )
        .fetch_one(&state.db_conn)
        .await
        .inspect_err(|e| error!("error inserting user: {:?}", e))?;

        let uuid = res.id.ok_or(UserUpsertError::Unreachable)?;

        Ok(uuid)
    }
}

#[derive(Deserialize, Debug)]
pub struct UpsertResult {
    id: Option<Uuid>,
}

impl From<sqlx::Error> for UserUpsertError {
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
