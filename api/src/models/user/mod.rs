use sqlx::types::Uuid;

#[derive(FromRow, Serialize, Deserialize, Debug)]
pub struct User {
    pub id: Uuid,
    pub gh_id: Option<i32>,
    pub gh_email: Option<String>,
    pub gh_login: String,
    pub gh_token: Option<String>,
    pub gh_avatar_url: Option<String>,
    pub email_verified: Option<bool>,
}
