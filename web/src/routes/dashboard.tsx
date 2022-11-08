import { LoaderArgs } from "@remix-run/node";
import { useLoaderData, Outlet } from "@remix-run/react";

import { getUser, redirectLogin } from "~/session.server";
import { AppShell } from "~/components/AppShell";

export const loader = async ({ request }: LoaderArgs) => {
  const user = await getUser(request);
  return user ?? redirectLogin(request.url);
};

export default function Dashboard() {
  const user = useLoaderData<typeof loader>();

  return (
    <AppShell user={user}>
      <div className="py-6">
        <div className="mx-auto px-4 sm:px-6 md:px-8">
          <h1 className="text-2xl font-semibold text-gray-900">Experiments</h1>
        </div>
        <div className="mx-auto px-4 sm:px-6 md:px-8">
          <Outlet />
        </div>
      </div>
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
