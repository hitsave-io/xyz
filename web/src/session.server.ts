import jwt_decode from "jwt-decode";
import { parseCookie } from "~/utils/cookie";
import { API } from "~/api";

export function redirectLogin(redirectUrl?: string) {
  const redirectParam = redirectUrl ? `?redirect=${redirectUrl}` : "";
  const params = {
    client_id: process.env.GH_CLIENT_ID || "",
    redirect_uri: `${process.env.HITSAVE_WEB_URL}/login${redirectParam}`,
    scope: "user:email",
  };

  const signInUrl = `https://github.com/login/oauth/authorize?${new URLSearchParams(
    params
  ).toString()}`;

  return new Response(null, {
    status: 302,
    headers: {
      Location: signInUrl,
    },
  });
}

// Extracts a cookie from the request, if present, and returns the parsed JWT.
// If not present, or the cookie does not contain a JWT, retruns null.
export function getSession(request: Request): string | null {
  const cookie = request.headers.get("Cookie");

  if (!cookie) {
    return null;
  } else {
    const parsed = parseCookie(cookie);
    if (!parsed.hasOwnProperty("jwt")) {
      return null;
    } else {
      return parsed.jwt;
    }
  }
}

// TODO: replace this with an autogenerated typescript type from Rust's `ts-rs`.
export interface User {
  id: string;
  gh_id: number;
  gh_email: string;
  gh_login: string;
  gh_avatar_url: string;
  email_verified: boolean;
}

export async function getUser(request: Request): Promise<User | null> {
  const jwt = getSession(request);
  if (!jwt) {
    return null;
  }

  const user = await API.fetch_protected("/user", jwt);

  if (!user) {
    return null;
  }

  if (user.status !== 200) {
    return null;
  } else {
    return user.json() as Promise<User>;
  }
}

// NOTE: this _does not_ validate the token. It just checks:
// 1. if a token exists
// 2. if the token is live (ie. has not expired)
export function hasUnexpiredJwt(request: Request): boolean {
  const jwt = getSession(request);
  if (!jwt) {
    return false;
  }

  const decoded: { exp?: string | number } = jwt_decode(jwt);
  const exp = decoded?.exp;
  if (!exp || typeof exp !== "number") {
    return false;
  } else {
    return exp <= Date.now();
  }
}
