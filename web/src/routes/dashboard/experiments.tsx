import { useEffect } from "react";
import shallow from "zustand/shallow";
import { LoaderArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";

import { API } from "~/api";
import { getSession, redirectLogin } from "~/session.server";
import { Experiment, useUiState } from "~/state/experiments";

import { ContextMenu } from "~/components/ContextMenu";
import { Table } from "~/components/Table";

export const loader = async ({ request }: LoaderArgs) => {
  const jwt = getSession(request);
  if (!jwt) {
    return redirectLogin(request.url);
  }

  const res = await API.fetch_protected("/eval?is_experiment=true", jwt);

  if (!res || res.status !== 200) {
    return redirectLogin(request.url);
  } else {
    return (await res.json()) as Experiment[];
  }
};

function safeSort<T>(comparator: (a: T, b: T) => number, arr: T[]): T[] {
  return [...arr].sort(comparator);
}

export default function Experiments() {
  const experiments = useLoaderData<typeof loader>() as Experiment[];
  const fromExps = useUiState((store) => store.fromExps);

  useEffect(() => {
    fromExps(experiments);
  }, []);

  const contextMenu = useUiState((store) => store.ui.contextMenu);
  const symbols = useUiState((store) => store.ui.symbols, shallow);
  const allSelected = Object.values(symbols)
    .map((s) => s.selectedVersions)
    .flat();

  const symbolVersions = Object.entries(symbols)
    .map(([name, symbol]) => {
      return symbol.versions.map((v) => {
        return {
          name,
          version: v,
        };
      });
    })
    .flat();

  const sortedSymbolVersions = safeSort((a, b) => {
    if (a.name === b.name) {
      return a.version.digest.localeCompare(b.version.digest);
    } else {
      return a.name.localeCompare(b.name);
    }
  }, symbolVersions);

  return (
    <div className="flex h-full">
      <div className="flex flex-col flex-1 px-3 overflow-hidden">
        <div className="-mx-3 h-full inline-block align-middle overflow-auto">
          <div className="inline-block min-w-full">
            {sortedSymbolVersions
              .filter((sv) => allSelected.includes(sv.version.digest))
              .map((symbol) => (
                <Table
                  key={symbol.version.digest}
                  symbol={symbol.name}
                  version={symbol.version}
                />
              ))}
          </div>
        </div>
      </div>

      {/* Context menu */}
      <div className="hidden md:block w-full max-w-xxs bg-white border-l border-gray-100 h-full overflow-y-auto p-3 text-xxs">
        <ContextMenu cxm={contextMenu} />
      </div>
    </div>
  );
}
