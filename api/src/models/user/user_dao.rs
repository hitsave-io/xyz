use super::{AddUser, User, UserError};
use crate::state::AppStateRaw;

use sqlx::Error;

#[async_trait]
pub trait IUser: std::ops::Deref<Target = AppStateRaw> {
    async fn insert_user(&self, user: &AddUser) -> Result<User, UserError> {
        let res = query_as!(
            User,
            r#"INSERT INTO users (email) VALUES ($1) RETURNING users.email"#,
            user.email
        )
        .fetch_one(&self.db_conn)
        .await
        .inspect_err(|e| error!("error inserting user: {:?}", e))?;

        Ok(res)
    }
}

impl From<sqlx::Error> for UserError {
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
