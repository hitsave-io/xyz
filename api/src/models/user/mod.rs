pub mod user_dao;
pub mod user_routes;

#[derive(FromRow, Serialize, Deserialize, Debug)]
pub struct User {
    pub email: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct AddUser {
    pub email: String,
}

#[derive(Debug)]
pub enum UserError {
    AlreadyExists,
    Sqlx(sqlx::Error),
}
