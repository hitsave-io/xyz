use crate::handlers::waitlist::WaitlistInsert;
use crate::middlewares::auth::Auth;
use crate::persisters::Persist;
use crate::state::State;

use sqlx::Error;

#[derive(Debug)]
pub enum WaitlistInsertError {
    AlreadyExists,
    Sqlx(sqlx::Error),
}

impl From<WaitlistInsertError> for actix_web::Error {
    fn from(e: WaitlistInsertError) -> Self {
        match e {
            WaitlistInsertError::AlreadyExists => {
                actix_web::error::ErrorConflict("Already on waitlist.")
            }
            WaitlistInsertError::Sqlx(e) => {
                log::error!("error inserting to waitlist: {:?}", e);
                actix_web::error::ErrorInternalServerError("unable to add to waitlist")
            }
        }
    }
}

#[async_trait]
impl Persist for WaitlistInsert {
    type Ret = ();
    type Error = WaitlistInsertError;

    async fn persist(self, _auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error> {
        let _res = query!(
            r#"
              INSERT INTO waitlist (email)
              VALUES ($1)
              RETURNING id
            "#,
            &self.email
        )
        .fetch_one(&state.db_conn)
        .await?;

        Ok(())
    }
}

impl From<sqlx::Error> for WaitlistInsertError {
    fn from(e: sqlx::Error) -> Self {
        log::error!("error: {:?}", e);
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
