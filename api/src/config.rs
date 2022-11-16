use crate::persisters::s3store::S3Store;
use crate::state::*;

use std::env;
use std::sync::Arc;

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct Config {
    pub database_url: String,
    pub port: u16,
    pub jwt_priv: String,
    pub gh_client_id: String,
    pub gh_client_secret: String,
    pub gh_user_agent: String,
    pub aws_s3_cred_file: String,
}

#[derive(Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
struct DbOptions {
    timeout: u64,
    #[serde(default)]
    server_timezone: String,
}

impl Config {
    pub fn parse_from_env() -> Self {
        // Todo: probably switch to the `config` crate which does all this cleanly.

        // Load environment variables from a .env file. This is used for dev workflows.
        dotenv::dotenv().ok();

        let mut env_vars: std::collections::HashMap<String, String> = env::vars().collect();

        // Note: it's okay to panic in places like this, because without these
        // env vars, we can't launch the server at all, and it only happens at startup.

        // Build the database URL from the various environment variables and secrets.
        let database_user = env_vars
            .remove("POSTGRES_USER")
            .expect("no database user environment variable present");
        let database_password_file = env_vars
            .remove("POSTGRES_PASSWORD_FILE")
            .expect("no database password file environment variable present");
        let database_host = env_vars
            .remove("POSTGRES_HOST")
            .expect("no database host environment variable present");
        let database_port = env_vars
            .remove("POSTGRES_PORT")
            .expect("no database port environment variable present");
        let database_name = env_vars
            .remove("POSTGRES_DB")
            .expect("no database name environment variable present");
        let database_password = std::fs::read_to_string(database_password_file)
            .expect("could not read database password file; does it exist?");
        let database_url = format!(
            "postgres://{}:{}@{}:{}/{}",
            database_user, database_password, database_host, database_port, database_name
        );

        let port = env_vars
            .remove("PORT")
            .expect("no port environment variable present")
            .parse::<u16>()
            .expect("invalid port");
        let jwt_priv_file = env_vars
            .remove("JWT_PRIV_FILE")
            .expect("no JWT_PRIV_FILE environment variable present");
        let gh_client_id = env_vars
            .remove("GH_CLIENT_ID")
            .expect("no GH_CLIENT_ID environment variable present");
        let gh_client_secret_file = env_vars
            .remove("GH_CLIENT_SECRET_FILE")
            .expect("no GH_CLIENT_SECRET_FILE environment variable present");
        let gh_user_agent = env_vars
            .remove("GH_USER_AGENT")
            .expect("no GH_USER_AGENT environment variable present");
        let aws_s3_cred_file = env_vars
            .remove("AWS_S3_CRED_FILE")
            .expect("no AWS_S3_CRED_FILE environment variable present");

        let jwt_priv = std::fs::read_to_string(jwt_priv_file)
            .expect("could not read jwt priv file; does it exist?");
        let gh_client_secret = std::fs::read_to_string(gh_client_secret_file)
            .expect("could not read gh client secret file; does it exist?");

        Config {
            database_url,
            port,
            jwt_priv,
            gh_client_id,
            gh_client_secret,
            gh_user_agent,
            aws_s3_cred_file,
        }
    }
    pub async fn into_state(self) -> AppStateRaw {
        info!("config: {:?}", self);
        let mut pool_options = PoolOptions::new();

        if let Some(opstr) = url::Url::parse(&self.database_url)
            .expect("Invalid SqlDB URL")
            .query()
        {
            if let Some(ops) = serde_qs::from_str::<DbOptions>(opstr)
                .map_err(|e| error!("serde_qs::from_str::<DbOptions> failed: {}", e))
                .ok()
            {
                pool_options =
                    pool_options.acquire_timeout(std::time::Duration::from_secs(ops.timeout));

                if !ops.server_timezone.is_empty() {
                    let key = if cfg!(feature = "mysql") {
                        "@@session.time_zone ="
                    } else if cfg!(feature = "postgres") {
                        "TIME ZONE"
                    } else {
                        panic!("sqlite can't set timezone!")
                    };
                    // UTC, +00:00, HongKong, etc
                    let set = format!("SET {} '{}'", key, ops.server_timezone.clone());

                    // cannot move out of `set_str`, a captured variable in an `Fn` closure
                    let set_str = unsafe { std::mem::transmute::<_, &'static str>(set.as_str()) };
                    std::mem::forget(set);
                    pool_options = pool_options.after_connect(move |conn, _meta| {
                        Box::pin(async move {
                            use crate::sqlx::Executor;
                            conn.execute(set_str).await.map(|_| ())
                        })
                    })
                }
            }
        }

        let db_conn = pool_options
            .connect(&self.database_url)
            .await
            .expect("sql open");

        let s3_store = S3Store::new().await;

        Arc::new(State {
            config: self,
            db_conn,
            s3_store,
        })
    }
    // generate and show config string
    pub fn show() {
        let de: Self = Default::default();
        println!("{}", serde_json::to_string_pretty(&de).unwrap())
    }
}

pub fn version_with_gitif() -> &'static str {
    // TODO: fix this vergen stuff.
    concat!(
        env!("CARGO_PKG_VERSION"),
        " ",
        // env!("VERGEN_GIT_COMMIT_DATE"),
        ": ",
        // env!("VERGEN_GIT_SHA_SHORT")
    )
}

#[derive(clap::Parser, Debug)]
// #[clap(name = "template")]
#[clap(version = version_with_gitif())]
pub struct Opts {
    // The number of occurrences of the `v/verbose` flag
    /// Verbose mode (-v, -vv, -vvv, etc.)
    #[clap(short, long, parse(from_occurrences))]
    pub verbose: u8,
}

impl Opts {
    pub fn parse_from_args() -> (JoinHandle, Self) {
        use clap::Parser;
        let opt: Self = Opts::parse();

        let level = match opt.verbose {
            0 => LevelFilter::Warn,
            1 => LevelFilter::Info,
            2 => LevelFilter::Debug,
            _more => LevelFilter::Trace,
        };

        let formater = BaseFormater::new()
            .local(true)
            .color(true)
            .level(4)
            .formater(format);
        let filter = BaseFilter::new()
            .starts_with(true)
            .notfound(true)
            .max_level(level)
            .chain(
                "sqlx",
                if opt.verbose > 1 {
                    LevelFilter::Debug
                } else {
                    LevelFilter::Warn
                },
            );

        let handle = NonblockLogger::new()
            .filter(filter)
            .unwrap()
            .formater(formater)
            .log_to_stdout()
            .map_err(|e| eprintln!("failed to init nonblock_logger: {:?}", e))
            .unwrap();

        info!("opt: {:?}", opt);

        (handle, opt)
    }
}

use nonblock_logger::{
    log::{LevelFilter, Record},
    BaseFilter, BaseFormater, FixedLevel, JoinHandle, NonblockLogger,
};

pub fn format(base: &BaseFormater, record: &Record) -> String {
    let level = FixedLevel::with_color(record.level(), base.color_get())
        .length(base.level_get())
        .into_colored()
        .into_coloredfg();

    format!(
        "[{} {}#{}:{} {}] {}\n",
        chrono::Local::now().format("%Y-%m-%d %H:%M:%S.%3f"),
        level,
        record.module_path().unwrap_or("*"),
        // record.file().unwrap_or("*"),
        record.line().unwrap_or(0),
        nonblock_logger::current_thread_name(),
        record.args()
    )
}
