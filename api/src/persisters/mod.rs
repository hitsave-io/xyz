pub mod api_key;
pub mod blob;
pub mod eval;
pub mod experiment;
pub mod s3store;
pub mod user;

use crate::middlewares::auth::Auth;
use crate::state::State;

/// Abstraction over the notion of a query.
///
/// Usually, we will implement this type on a something like a params struct which can be extracted
/// from a handler (i.e. it will also implement `FromRequest`). In the handler, we can then simply
/// call `fetch` on the query params to retrieve the relevant model instance.
#[async_trait]
pub trait Query {
    /// The type returned when the query resolves.
    type Resolve;
    /// Error type returned if the query fails.
    type Error;
    /// Fetches the model instance from underlying storage.
    ///
    /// Usually, this is where the raw SQL query lives.
    async fn fetch(self, auth: Option<&Auth>, state: &State) -> Result<Self::Resolve, Self::Error>;
}

/// Abstraction over the notion of persisting data.
///
/// Usually, we will implement this type on an insertable item. Often, insertable items have a
/// subset of the fields of a model instance (e.g. they don't have a uuid assigned yet, as this
/// happens inside the DB).
#[async_trait]
pub trait Persist {
    /// The return type used to indicate a successful attempt to persist the item.
    type Ret;
    /// Error type returned from unsuccessful attempts to persist the item.
    type Error;
    /// Persist the value to the database passed in by `conn`.
    async fn persist(self, auth: Option<&Auth>, state: &State) -> Result<Self::Ret, Self::Error>;
}
