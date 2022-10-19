use crate::handlers::eval::Params;
use crate::middlewares::api_auth::Auth;
use crate::models::eval::{Eval, EvalError};
use crate::persisters::s3store::BlobMetadata;
use crate::persisters::{Persist, Query};
use crate::state::State;
use actix_web::web;
use sqlx::{
    types::{JsonValue, Uuid},
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
    pub content_hash: String,
    pub content_length: i64,
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
        let auth = auth.ok_or(EvalError::Unauthorized)?;

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
            auth.key,
            self.content_hash,
        )
        .fetch_one(&mut tx)
        .await?;

        // Insert new eval.
        // NOTE: the "ON CONFLICT" clause in the below query would prevent insertions if the row
        // already existed and caused a conflict. But we don't get conflicts right now because
        // there is now unique constraint enforced across the three critical rows (fn_key, fn_hash,
        // args_hash).
        let eval_res = query_as!(
            EvalInsertResult,
            r#"
            WITH s AS (
                SELECT id
                FROM evals
                WHERE user_id = user_from_key($6)
                AND fn_key = $1
                AND fn_hash = $2
                AND args_hash = $4
            ), i AS (
                INSERT INTO evals (fn_key, fn_hash, args, args_hash, blob_id, user_id) 
                VALUES ($1, $2, $3, $4, $5, user_from_key($6))
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
            blob_res.id.expect("huh"),
            auth.key
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

        println!("{:?}", params);

        let res = query_as!(
            Eval,
            r#"
            SELECT fn_key, fn_hash, args, args_hash, content_hash 
            FROM evals e 
            JOIN blobs b
                ON b.id = e.blob_id
            WHERE   (fn_key = $1 OR $1 IS NULL)
                AND (fn_hash = $2 OR $2 IS NULL)
                AND (args_hash = $3 OR $3 IS NULL)
                AND e.user_id = user_from_key($4)
            "#,
            params.fn_key,
            params.fn_hash,
            params.args_hash,
            auth.key,
        )
        .fetch_all(&state.db_conn)
        .await?;

        Ok(res)
    }
}
