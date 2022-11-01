import { LoaderFunction, redirect } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";

export const loader: LoaderFunction = async ({ request }) => {
  const cookie = request.headers.get("Cookie");

  if (!cookie) {
    return redirect("http://127.0.0.1:3000/");
  } else {
    const parsed = parseCookie(cookie);
    const user = await fetch("http://127.0.0.1:8080/user", {
      headers: {
        Authorization: `Bearer ${parsed.jwt}`,
      },
    });

    if (user.status != 200) {
      throw new Error("uh-oh, it's fooked");
    } else {
      return await user.json();
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
    </>
  );
}

export function ErrorBoundary({ error }: { error: Error }) {
  console.error(error);
  return <p>{error.message}</p>;
}
