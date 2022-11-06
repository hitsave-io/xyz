import { LoaderArgs, redirect } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";

export const loader = async ({ request }: LoaderArgs) => {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");

  const res = await fetch(`http://127.0.0.1:8080/user/login?code=${code}`, {
    method: "post",
  });

  if (res.status == 200) {
    const jwt = await res.text();
    console.log(jwt);

    return redirect("http://127.0.0.1:3000/dashboard/experiments", {
      headers: {
        "Set-Cookie": `jwt=${jwt}; HttpOnly; Max-Age=${60 * 60 * 24 * 30};`,
      },
    });
  } else {
    // TODO
    return "1234";
  }
};

export default function LoginPage() {
  useLoaderData<typeof loader>();
}
