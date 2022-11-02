use crate::handlers::experiment::Params;
use crate::middlewares::api_auth::Auth;
use crate::models::eval::{Eval, EvalError};
use crate::persisters::Query;
use crate::state::State;

use actix_web::web;

// TODO: we shouldn't really have this. It's duplicative of the eval persister.
//
// To get it working DRY, we need:
// - unified auth (i.e. a query can accept either JWT or API based auth)
// - a general params object for querying evals, which lives in `persisters::eval` module
// - special params objects for each API handler, which can be converted to the general params
//   object that lives in `persisters::eval`
#[async_trait]
impl Query for web::Query<Params> {
    type Resolve = Vec<Eval>;
    type Error = EvalError;

    async fn fetch(self, auth: Option<&Auth>, state: &State) -> Result<Self::Resolve, Self::Error> {
        let auth = auth.ok_or(EvalError::Unauthorized)?;
        let params = self.into_inner();

        let res = query_as!(
            Eval,
            r#"
            SELECT fn_key, fn_hash, args, args_hash, content_hash, is_experiment, start_time, 
                elapsed_process_time, accesses
            FROM evals e
            JOIN blobs b
                ON b.id = e.blob_id
            WHERE e.user_id = user_from_key($1)
                AND is_experiment = true  
            ORDER BY start_time DESC
            LIMIT $2
            "#,
            auth.key,
            params.count,
        )
        .fetch_all(&state.db_conn)
        .await?;

        Ok(res)
    }
}
