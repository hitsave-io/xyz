use super::{AddUser, User};
use crate::state::AppStateRaw;

#[async_trait]
pub trait IUser: std::ops::Deref<Target = AppStateRaw> {
    async fn insert_user(&self, user: &AddUser) -> sqlx::Result<Option<User>> {
        query_as!(
            User,
            r#"INSERT INTO users (email) VALUES ($1) RETURNING users.email"#,
            user.email
        )
        .fetch_optional(&self.db_conn)
        .await
    }
}

impl IUser for &AppStateRaw {}
