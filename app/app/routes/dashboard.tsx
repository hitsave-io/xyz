import { LoaderFunction, redirect } from "@remix-run/node";
import { useLoaderData, Outlet } from "@remix-run/react";

const jwt = async (request: Request): string => {
  const cookie = request.headers.get("Cookie");

  if (!cookie) {
    throw Error("Unauthorized");
  } else {
    const parsed = parseCookie(cookie);
    if (!parsed.hasOwnProperty("jwt")) {
      throw Error("Unauthorized");
    } else {
      return parsed.jwt;
    }
  }
};

const parseCookie = (cookie: string): { [key: string]: string } => {
  return cookie
    .split(";")
    .map((v) => v.split("="))
    .reduce<{ [key: string]: string }>((acc, v) => {
      acc[decodeURIComponent(v[0].trim())] = decodeURIComponent(v[1].trim());
      return acc;
    }, {});
};

export const loader: LoaderFunction = async ({ request }) => {
  const token = await jwt(request);
  const user = await fetch("http://127.0.0.1:8080/user", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (user.status != 200) {
    throw new Error("Unable to load user data.");
  } else {
    return await user.json();
  }
};

export default function Dashboard() {
  const user = useLoaderData();
  return (
    <>
      <h1>Your Hitsave Dashboard</h1>
      <h2>
        Welcome {user.gh_login} ({user.gh_email})
      </h2>
      <img
        src={user.gh_avatar_url}
        width={150}
        style={{ borderRadius: 9999 }}
      />
      <Outlet />
    </>
  );
}

export function ErrorBoundary({ error }: { error: Error }) {
  console.error(error);
  return <p>{error.message}</p>;
}
