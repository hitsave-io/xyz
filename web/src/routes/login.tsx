import { useEffect } from "react";
import { HeadersFunction, LoaderArgs, redirect } from "@remix-run/node";
import { useLoaderData, useSearchParams } from "@remix-run/react";
import { cors } from "remix-utils";

import { API } from "~/api";

// If you don't add this, it seems that the headers we added in `loader` just
// get dropped, or overwritten somewhere in a merge operation.
export const headers: HeadersFunction = ({ loaderHeaders }) => loaderHeaders;

export const loader = async ({ request }: LoaderArgs) => {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const redirectUrl = url.searchParams.get("redirect") ?? "/dashboard";

  // If a `client_loopback` params is present, it means that the login was initiated
  // Python client, and we should respond from the user's web browser with a web fetch
  // to the temporary localhost server running in Python, to inform that the sign in was
  // successful.
  const clientLoopbackUrl = url.searchParams.get("client_loopback");
  console.log("client loopback url is: ", clientLoopbackUrl);

  // Instruct the HitSave API to attempt to retrieve the user's login details with the
  // provided `code`.
  const res = await API.fetch(`/user/login?code=${code}`, {
    method: "post",
  });

  if (res.status == 200) {
    const jwt = await res.text();

    const headers = {
      "Set-Cookie": `jwt=${jwt}; HttpOnly; Max-Age=${
        60 * 60 * 24 * 30
      }; domain=${process.env.HITSAVE_WEB_HOST}`,
      "Access-Control-Allow-Origin": "http://127.0.0.1",
    };

    if (!clientLoopbackUrl) {
      // This is an attempt to access a protected page - we don't want to waste any time
      // showing a 'successfully logged in page', so just redirect to their desired URL.
      return redirect(redirectUrl, { headers });
    }

    // If we get here, then the login was initiated by the Python client. We would like to
    // display a success message, and send a message to the local Python mini-server from
    // the browser.
    const response = new Response(jwt, { headers });
    const responseWithCors = await cors(request, response, {
      origin: true,
    });
    console.log("about to return this response: ", responseWithCors);
    return responseWithCors;
  } else {
    throw new Error("Unable to log you in.");
  }
};

export default function LoginPage() {
  const jwt = useLoaderData<typeof loader>();
  const [searchParams] = useSearchParams();
  const clientLoopbackUrl = searchParams?.get("client_loopback");

  useEffect(() => {
    if (clientLoopbackUrl) {
      const url = new URL(`${clientLoopbackUrl}?jwt=${jwt}`);
      fetch(url, { method: "get" });
    }
  });

  return <>{clientLoopbackUrl && <>Successfully logged in.</>}</>;
}
