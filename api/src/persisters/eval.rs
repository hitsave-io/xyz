use crate::handlers::eval::Params;
use crate::middlewares::auth::Auth;
use crate::models::eval::{Eval, EvalError};
use crate::persisters::s3store::BlobMetadata;
use crate::persisters::{Persist, Query};
use crate::state::State;
use actix_web::web;
use sqlx::{
    types::{
        chrono::{DateTime, Utc},
        JsonValue, Uuid,
    },
    Error,
};

impl From<Error> for EvalError {
    fn from(e: Error) -> Self {
        Self::Sqlx(e)
    }
}

#[derive(Deserialize, Debug)]
pub struct EvalInsert {
    pub fn_key: String,
    pub fn_hash: String,
    pub args: Option<JsonValue>,
    pub args_hash: String,
    pub result_json: JsonValue,
    pub content_hash: String,
    pub content_length: i64,
    pub is_experiment: bool,
    pub start_time: DateTime<Utc>,
    pub elapsed_process_time: i64,
}

struct EvalInsertResult {
    id: Option<Uuid>,
}

struct BlobInsertResult {
    id: Option<i64>,
}

impl BlobMetadata for EvalInsert {
    fn content_length(&self) -> i64 {
        self.content_length
    }
    fn content_hash(&self) -> &str {
        &self.content_hash
    }
}

#[async_trait]
impl Persist for EvalInsert {
    type Ret = Uuid;
    type Error = EvalError;

    async fn persist(self, auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error> {
        let api_key = auth
            .ok_or(EvalError::Unauthorized)?
            .api_key()
            .ok_or(EvalError::Unauthorized)?;

        // Use a transaction as we have to modify two tables.
        let mut tx = state.db_conn.begin().await?;

        // Insert blob.
        let blob_res = query_as!(
            BlobInsertResult,
            r#"
            WITH s AS (
                SELECT id 
                FROM blobs 
                WHERE user_id = user_from_key($1) 
                AND content_hash = $2
            ), i AS (
                INSERT INTO blobs (user_id, content_hash)
                VALUES (user_from_key($1), $2)
                ON CONFLICT DO NOTHING
                RETURNING id
            )
            SELECT id
            FROM i UNION ALL
            SELECT id
            FROM s
            "#,
            api_key,
            self.content_hash,
        )
        .fetch_one(&mut tx)
        .await?;

        // Insert new eval.
        // NOTE: the "ON CONFLICT" clause in the below query would prevent insertions if the row
        // already existed and caused a conflict. But we don't get conflicts right now because
        // there is now unique constraint enforced across the three critical rows (fn_key, fn_hash,
        // args_hash).
        // TODO: but what if you attempt an upsert which changes the value of `is_experiment`?!?
        let eval_res = query_as!(
            EvalInsertResult,
            r#"
            WITH s AS (
                SELECT id
                FROM evals
                WHERE user_id = user_from_key($10)
                AND fn_key = $1
                AND fn_hash = $2
                AND args_hash = $4
            ), i AS (
                INSERT INTO evals (fn_key, fn_hash, args, args_hash, result_json, is_experiment, start_time, 
                    elapsed_process_time, blob_id, user_id) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, user_from_key($10))
                ON CONFLICT DO NOTHING
                RETURNING id
            )
            SELECT id
            FROM i UNION ALL
            SELECT id
            FROM s
            "#,
            self.fn_key,
            self.fn_hash,
            self.args,
            self.args_hash,
            self.result_json,
            self.is_experiment,
            self.start_time,
            self.elapsed_process_time,
            blob_res.id.expect("huh"),
            api_key
        )
        .fetch_one(&mut tx)
        .await?;

        // Commit transaction.
        tx.commit().await?;

        Ok(eval_res.id.expect("huh"))
    }
}

#[async_trait]
impl Query for web::Query<Params> {
    type Resolve = Vec<Eval>;
    type Error = EvalError;

    async fn fetch(self, auth: Option<&Auth>, state: &State) -> Result<Self::Resolve, Self::Error> {
        let auth = auth.ok_or(EvalError::Unauthorized)?;

        let params = self.into_inner();

        if let Some(true) = params.poll {
            query!(
                r#"
            UPDATE evals e
            SET accesses = accesses + 1
            WHERE (fn_key = $1 OR $1 IS NULL)
                AND (fn_hash = $2 OR $2 IS NULL)
                AND (args_hash = $3 OR $3 IS NULL)
                AND (is_experiment = $4 OR $4 IS NULL)
                AND e.user_id = get_user_id($5, $6)
            "#,
                params.fn_key,
                params.fn_hash,
                params.args_hash,
                params.is_experiment,
                auth.jwt().map(|c| c.sub),
                auth.api_key(),
            )
            .execute(&state.db_conn)
            .await?;
        }

        let res = query_as!(
            Eval,
            r#"
            SELECT fn_key, fn_hash, args, args_hash, result_json, content_hash, is_experiment, start_time, 
                elapsed_process_time, accesses 
            FROM evals e 
            JOIN blobs b
                ON b.id = e.blob_id
            WHERE   (fn_key = $1 OR $1 IS NULL)
                AND (fn_hash = $2 OR $2 IS NULL)
                AND (args_hash = $3 OR $3 IS NULL)
                AND (is_experiment = $4 OR $4 IS NULL)
                AND e.user_id = get_user_id($5, $6)
            "#,
            params.fn_key,
            params.fn_hash,
            params.args_hash,
            params.is_experiment,
            auth.jwt().map(|c| c.sub),
            auth.api_key(),
        )
        .fetch_all(&state.db_conn)
        .await?;

        Ok(res)
    }
}
