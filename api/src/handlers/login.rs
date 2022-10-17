use crate::models::user::user_dao::{AddUser, IUser, UserInsertError};
use crate::state::AppState;
use crate::CONFIG;

pub async fn login_handler(code: String, state: &AppState) -> Result<String, LoginError> {
    let access_token = get_access_token(&code).await.map_err(|e| {
        log::error!("error retrieving GitHub access token: {:?}", e);
        LoginError::AccessTokenNotGranted
    })?;

    println!("{}", access_token);

    let (user_info, emails) = get_user_info(&access_token).await.map_err(|e| {
        log::error!("error retrieving Github user info {:?}", e);
        LoginError::UserInfoNotAvailable
    })?;

    let add_user = build_add_user(&user_info, emails, &access_token)?;

    let new_user_id = state.get_ref().insert_user(&add_user).await?;

    let jwt = generate_jwt(new_user_id)?;

    Ok(jwt)
}

#[derive(Deserialize, Debug)]
struct GithubAccessTokenResponse {
    access_token: String,
}

async fn get_access_token(code: &str) -> Result<String, LoginError> {
    let client = reqwest::Client::new();

    let res = client
        .post("https://github.com/login/oauth/access_token")
        .header(reqwest::header::ACCEPT, "application/json")
        .query(&[
            ("client_id", &CONFIG.gh_client_id),
            ("client_secret", &CONFIG.gh_client_secret),
            ("code", &code.to_string()),
        ])
        .send()
        .await?
        .json::<GithubAccessTokenResponse>()
        .await?;

    Ok(res.access_token)
}

#[derive(Deserialize, Debug)]
struct GithubUserInfo {
    id: i32,
    login: String,
    avatar_url: String,
}

fn build_add_user(
    user: &GithubUserInfo,
    mut emails: Vec<GithubEmail>,
    token: &String,
) -> Result<AddUser, LoginError> {
    let emails = emails
        .drain(0..)
        .filter(|e| e.primary == true)
        .collect::<Vec<GithubEmail>>();

    let primary_email = emails.first().ok_or(LoginError::NoPrimaryEmail)?;

    let user = AddUser {
        gh_id: user.id,
        gh_email: primary_email.email.clone(),
        gh_login: user.login.clone(),
        gh_token: token.to_string(),
        gh_avatar_url: user.avatar_url.clone(),
        email_verified: primary_email.verified,
    };

    Ok(user)
}

#[derive(Deserialize, Debug)]
struct GithubEmail {
    email: String,
    verified: bool,
    primary: bool,
}

async fn get_user_info(
    access_token: &str,
) -> Result<(GithubUserInfo, Vec<GithubEmail>), LoginError> {
    let client = reqwest::Client::new();

    let user = client
        .get("https://api.github.com/user")
        .header(reqwest::header::USER_AGENT, &CONFIG.gh_user_agent)
        .header(reqwest::header::ACCEPT, "application/json")
        .header(
            reqwest::header::AUTHORIZATION,
            format!("Bearer {}", access_token),
        )
        .send()
        .await?
        .json::<GithubUserInfo>()
        .await?;

    let emails = client
        .get("https://api.github.com/user/emails")
        .header(reqwest::header::USER_AGENT, &CONFIG.gh_user_agent)
        .header(reqwest::header::ACCEPT, "application/json")
        .header(
            reqwest::header::AUTHORIZATION,
            format!("Bearer {}", access_token),
        )
        .send()
        .await?
        .json::<Vec<GithubEmail>>()
        .await?;

    Ok((user, emails))
}

#[derive(Debug)]
pub enum LoginError {
    GHComms(reqwest::Error),
    JwtError(jsonwebtoken::errors::Error),
    UserInsert(UserInsertError),
    AccessTokenNotGranted,
    UserInfoNotAvailable,
    NoPrimaryEmail,
}

impl From<reqwest::Error> for LoginError {
    fn from(e: reqwest::Error) -> Self {
        Self::GHComms(e)
    }
}

impl From<UserInsertError> for LoginError {
    fn from(e: UserInsertError) -> Self {
        Self::UserInsert(e)
    }
}

impl From<jsonwebtoken::errors::Error> for LoginError {
    fn from(e: jsonwebtoken::errors::Error) -> Self {
        Self::JwtError(e)
    }
}

#[derive(Serialize, Deserialize)]
pub struct Claims {
    sub: sqlx::types::Uuid,
    exp: i64,
}

fn generate_jwt(user_uuid: sqlx::types::Uuid) -> Result<String, LoginError> {
    use chrono::{DateTime, Duration, Utc};
    use jsonwebtoken::{encode, EncodingKey, Header};

    let exp: DateTime<Utc> = Utc::now() + Duration::days(30);

    let claims = Claims {
        sub: user_uuid,
        exp: exp.timestamp(),
    };

    let key = &*CONFIG.jwt_priv.as_bytes();
    let token = encode(&Header::default(), &claims, &EncodingKey::from_secret(key))?;

    Ok(token)
}
