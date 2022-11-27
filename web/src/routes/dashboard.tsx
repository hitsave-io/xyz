import { LoaderArgs } from "@remix-run/node";
import { useLoaderData, Outlet } from "@remix-run/react";

import { getUser, redirectLogin } from "~/session.server";
import { AppShell } from "~/components/AppShell";
import { registerPageload } from "~/db";

export const loader = async ({ request }: LoaderArgs) => {
  registerPageload(request);

  const user = await getUser(request);
  return user ?? redirectLogin(request.url);
};

export default function Dashboard() {
  const user = useLoaderData<typeof loader>();

  return (
    <AppShell user={user}>
      <Outlet />
    </AppShell>
  );
}

export function ErrorBoundary({ error }: { error: Error }) {
  console.error(error);
  return <p>{error.message}</p>;
}

export function CatchBoundary() {
  return (
    <div>
      <h2>We couldn't find that page. Sorry!</h2>
    </div>
  );
}
