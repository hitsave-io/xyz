use crate::handlers::waitlist::WaitlistInsert;
use crate::middlewares::auth::Auth;
use crate::persisters::Persist;
use crate::state::State;

use sqlx::types::Uuid;

#[derive(Debug)]
pub enum WaitlistInsertError {
    Sqlx(sqlx::Error),
}

impl From<WaitlistInsertError> for actix_web::Error {
    fn from(e: WaitlistInsertError) -> Self {
        log::error!("error inserting to waitlist: {:?}", e);
        actix_web::error::ErrorInternalServerError("unable to add to waitlist")
    }
}

#[derive(Deserialize, Debug)]
struct InsertResult {
    id: Uuid,
}

#[async_trait]
impl Persist for WaitlistInsert {
    type Ret = Uuid;
    type Error = WaitlistInsertError;

    async fn persist(self, _auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error> {
        let res = query_as!(
            InsertResult,
            r#"
                INSERT INTO waitlist (email)
                VALUES ($1)
                RETURNING id
                "#,
            &self.email
        )
        .fetch_one(&state.db_conn)
        .await
        .map_err(|e| WaitlistInsertError::Sqlx(e))?;

        Ok(res.id)
    }
}
