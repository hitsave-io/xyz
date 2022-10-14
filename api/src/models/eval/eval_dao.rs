use super::{Eval, EvalError};
use crate::state::AppStateRaw;
use sqlx::types::Uuid;

impl From<sqlx::Error> for EvalError {
    fn from(e: sqlx::Error) -> Self {
        Self::Sqlx(e)
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct QueryParams {
    fn_key: String,
    fn_hash: String,
    args_hash: String,
}

#[async_trait]
pub trait IEval: std::ops::Deref<Target = AppStateRaw> {
    async fn get_eval_by_id(&self, id: Uuid) -> sqlx::Result<Eval> {
        let eval = query_as!(
            Eval,
            r#"SELECT fn_key, fn_hash, args, args_hash, result FROM evals WHERE id = $1"#,
            id
        )
        .fetch_one(&self.db_conn)
        .await?;

        Ok(eval)
    }

    async fn get_evals_by_params(
        &self,
        params: QueryParams,
        api_key: &str,
    ) -> Result<Vec<Eval>, EvalError> {
        let evals = query_as!(
            Eval,
            r#"
            SELECT fn_key, fn_hash, args, args_hash, result FROM evals 
            WHERE fn_key = $1 
              AND fn_hash = $2 
              AND args_hash = $3
              AND user_id = (SELECT id FROM auth_api_key($4))
              "#,
            params.fn_key,
            params.fn_hash,
            params.args_hash,
            api_key
        )
        .fetch_all(&self.db_conn)
        .await
        .map_err(|e| {
            error!("error retrieving evals from database: {:?}", e);
            EvalError::NotFound(e)
        })?;

        Ok(evals)
    }

    async fn insert_eval(&self, eval: &Eval, api_key: &str) -> sqlx::Result<String> {
        let row = query_as!(
            ReturnedInsert,
            r#"
            INSERT INTO evals (fn_key, fn_hash, args, args_hash, result, user_id) 
            SELECT $1, $2, $3, $4, $5, id FROM auth_api_key($6) LIMIT 1
            RETURNING evals.id"#,
            eval.fn_key,
            eval.fn_hash,
            eval.args,
            eval.args_hash,
            eval.result,
            api_key
        )
        .fetch_one(&self.db_conn)
        .await?;

        Ok(row.id.to_string())
    }
}

#[derive(FromRow)]
struct ReturnedInsert {
    id: Uuid,
}

impl IEval for &AppStateRaw {}
