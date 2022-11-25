import { LoaderArgs } from "@remix-run/node";
import { useLoaderData, Outlet } from "@remix-run/react";

import { getUser, redirectLogin, User } from "~/session.server";
import { AppShell } from "~/components/AppShell";
import { ContextMenuKind, useUiState } from "~/state/experiments";

export const loader = async ({ request }: LoaderArgs) => {
  const user = await getUser(request);
  return user ?? redirectLogin(request.url);
};

export default function Dashboard() {
  const user = useLoaderData<typeof loader>() as User;
  const setContextMenu = useUiState((store) => store.setContextMenu);

  return (
    <AppShell
      user={user}
      onClickTitle={() =>
        setContextMenu({
          __kind__: ContextMenuKind.Experiment,
        })
      }
    >
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
