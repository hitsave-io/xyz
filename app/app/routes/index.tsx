import { useLoaderData } from "@remix-run/react";

export const loader = async () => {
  const query_params = {
    client_id: "b7d5bad7787df04921e7",
    redirect_uri: "http://127.0.0.1:3000/login",
    scope: "user:email",
  };

  const url = `https://github.com/login/oauth/authorize?${new URLSearchParams(
    query_params
  ).toString()}`;

  return url;
};

export default function Index() {
  const url = useLoaderData<typeof loader>();
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", lineHeight: "1.4" }}>
      <h1>Welcome to HitSave</h1>
      <a href={url}>Login with Github</a>
    </div>
  );
}
