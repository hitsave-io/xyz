import { LoaderArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";

export const loader = async ({ request }: LoaderArgs) => {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");

  const res = await fetch(`http://127.0.0.1:8080/user/login?code=${code}`, {
    method: "post",
  });
  const jwt = res.text();
  console.log(jwt);
  return jwt;
};

export default function LoginPage() {
  const data = useLoaderData();
  return <p>{data}</p>;
}
