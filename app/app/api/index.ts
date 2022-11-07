// For now, this is a thin wrapper around the browser `fetch` method. We expose
// a `fetch` method which works exactly the same way, but automatically prepends
// the right `base_url` for the HitSave API server, based on the value of the
// env variable `HITSAVE_API_URL`.

class APIClass {
  baseUrl: string;

  constructor() {
    // Note: in dev mode, this constructor runs on every request, because of
    // how Remix does hot reloads. But in production, `APIClass` will be a
    // singleton, and the constructor will only run once on startup.
    // https://remix.run/docs/en/v1/other-api/serve
    this.baseUrl = process.env.HITSAVE_API_URL || "";
  }

  async fetch(route: string, requestInit?: RequestInit) {
    return fetch(`${this.baseUrl}${route}`, requestInit);
  }

  // Applies the passed JWT to the headers. If the passed JWT is falsey, then we
  // early return with an error, without sending the request to the API at all.
  async fetch_protected(
    route: string,
    jwt: string | null,
    requestInit?: RequestInit
  ) {
    if (!jwt) {
      throw new Error("unauthorized");
    }

    const req = {
      ...requestInit,
      headers: {
        ...requestInit?.headers,
        Authorization: `Bearer ${jwt}`,
      },
    };

    return this.fetch(route, req);
  }
}

export const API = new APIClass();
