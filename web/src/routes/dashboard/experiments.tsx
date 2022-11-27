import { useState } from "react";
import { LoaderArgs, LoaderFunction } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { API } from "~/api";
import { Show, VisualObject, Arg } from "../../components/visual";
import { getSession, redirectLogin } from "~/session.server";

interface Experiment {
  fn_key: string;
  fn_hash: string;
  args: Arg[];
  args_hash: string;
  result_json: VisualObject;
  content_hash: string;
  is_experiment: boolean;
  start_time: string;
  elapsed_process_time: number;
  accesses: number;
}

interface ExperimentTable {
  fn_key: string;
  args: { [argName: string]: Arg };
  experiments: Experiment[];
}

/* Note on which time pretty-printing library to use:

[On the moment website][1] they say you should not use it for new projects.
So I (EWA) tried using [luxon][2], but they don't have good [duration pretty printing][3],
so I switched back to using moment. There is also time-ago but whatever.

[1]: https://momentjs.com/docs/#/-project-status/
[2]: https://moment.github.io/luxon/#/?id=luxon
[3]: https://github.com/moment/luxon/issues/1134

*/

import moment from "moment";

function ppTimeAgo(isostring: string) {
  // luxon: return DateTime.fromISO(experiment.start_time).toRelative()
  return moment(isostring).fromNow();
}

function ppDuration(durationNanoseconds: number) {
  const durationSeconds = durationNanoseconds * 1e-9;
  // luxon: return Duration.fromMillis( experiment.elapsed_process_time * 1e-6 ).toHuman()
  // alternative: humanize-duration https://github.com/EvanHahn/HumanizeDuration.js
  // moment: return moment.duration(durationMiliseconds).humanize()
  return `${durationSeconds.toPrecision(2)} seconds`;
}

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

function processFns(exps: Experiment[]): ExperimentTable[] {
  const tables: { [key: string]: ExperimentTable } = {};
  for (const exp of exps) {
    const fk = exp.fn_key;

    if (!tables.hasOwnProperty(fk)) {
      tables[fk] = { fn_key: fk, args: {}, experiments: [] };
    }

    const table = tables[fk];
    for (const arg of exp.args) {
      // check that arg.name is in table.args
      if (!table.args.hasOwnProperty(arg.name)) {
        table.args[arg.name] = arg;
      }
    }

    table.experiments.push(exp);
    table.experiments.sort();
  }

  return Object.entries(tables)
    .map(([_, v]) => v)
    .sort();
}

function getArgs(exp: Experiment): Arg[] {
  return exp.args;
}

const parseFnKey = (fnKey: string): [string, string] => {
  const split = fnKey.split(":");
  if (split.length !== 2) {
    return [fnKey, ""];
  } else {
    return split as [string, string];
  }
};

export default function Experiments() {
  const experiments = useLoaderData<typeof loader>() as Experiment[];

  const tables = processFns(experiments).sort((t1, t2) => {
    if (t1.fn_key >= t2.fn_key) {
      return 1;
    } else {
      return -1;
    }
  });

  console.log(tables);

  return (
    <div className="max-h-full py-6">
      <div className="mx-auto px-4 sm:px-6 md:px-8">
        <h1 className="text-2xl font-semibold text-gray-900">
          Experiments
          {experiments.length && (
            <span className="text-gray-400 text-sm font-normal">
              {" "}
              ({experiments.length})
            </span>
          )}
        </h1>
      </div>
      <div className="mx-auto px-4 sm:px-6 md:px-8">
        <div className="mt-8 flex flex-col">
          <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
            <div className="inline-block min-w-full py-2 align-middle">
              <div className="shadow-sm ring-1 ring-black ring-opacity-5">
                {tables.map((table) => (
                  <ExperimentTable table={table} key={table.fn_key} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface TableProps {
  table: ExperimentTable;
}

const ExperimentTable: React.FC<TableProps> = ({ table }) => {
  const [open, setOpen] = useState(false);
  const fnKey = parseFnKey(table.fn_key);
  const argList = Object.entries(table.args)
    .map(([_, arg]) => arg)
    .sort();
  return (
    <table
      className="table-fixed w-full divide-y divide-gray-300 border-separate"
      style={{ borderSpacing: 0 }}
      key={table.fn_key}
    >
      <thead>
        <tr className="cursor-pointer" onClick={() => setOpen((o) => !o)}>
          <th
            scope="col"
            className="sticky top-0 w-64 z-10 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8"
          >
            <FnKey module={fnKey[0]} functionName={fnKey[1]} />
          </th>
          {argList.map((arg, argIdx) => (
            <th
              scope="col"
              className="sticky top-0 w-48 z-10 border-b border-gray-300 bg-gray-50 bg-opacity-75 px-3 py-3.5 text-center text-xs font-normal font-mono whitespace-nowrap backdrop-blur backdrop-filter"
              key={arg.name}
            >
              {argIdx === 0 && (
                <span className="font-mono text-sm text-gray-500">{"(  "}</span>
              )}
              <span className="whitespace-nowrap rounded-lg bg-gray-100 px-2 py-1 leading-6 text-gray-500 shadow-md hover:shadow-lg hover:bg-white hover:text-blue-600 cursor-pointer select-none">
                {arg.name}
              </span>
              {argIdx + 1 < argList.length && <>{" ,"}</>}
              {argIdx + 1 === argList.length && (
                <span className="font-mono text-sm text-gray-500">{"  )"}</span>
              )}
            </th>
          ))}
          <th
            scope="col"
            className="sticky top-0 w-96 z-10 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8 whitespace-nowrap"
          >
            returns
          </th>
          <th className="sticky top-0 w-auto z-10 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8 whitespace-nowrap"></th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-200 bg-white">
        {open &&
          table.experiments.map((experiment) => {
            return (
              <tr
                key={`${experiment.fn_hash}${experiment.args_hash}${experiment.fn_key}`}
                className="hover:bg-gray-50 cursor-pointer"
              >
                <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-mono font-medium text-gray-400 sm:pl-6 lg:pl-8 truncate">
                  {experiment.fn_hash.slice(0, 10)}
                </td>
                {argList.map((argCol) => {
                  const arg = getArgs(experiment).find(
                    (a) => a.name === argCol.name
                  );

                  return (
                    <td
                      key={argCol.name}
                      className="whitespace-nowrap px-3 py-4 font-mono text-sm text-gray-500 text-center"
                    >
                      {arg !== undefined ? <Show o={arg.value} /> : "null"}
                    </td>
                  );
                })}
                <td className="truncate px-3 py-4 text-sm text-gray-500 sm:pl-6 lg:pl-8">
                  {<Show o={experiment.result_json} />}
                </td>
                <td className="w-auto"></td>
              </tr>
            );
          })}
      </tbody>
    </table>
  );
};

interface FnKeyProps {
  module: string;
  functionName: string;
}

const FnKey: React.FC<FnKeyProps> = ({ module, functionName }) => {
  return (
    <>
      <span className="whitespace-nowrap rounded-l-lg bg-gray-100 px-2 py-1 leading-6 text-gray-400 shadow-md hover:shadow-lg hover:bg-gray-200 cursor-pointer select-none">
        {module}
      </span>
      <span className="whitespace-nowrap rounded-r-lg border-l-2 border-white bg-sky-700 px-2 py-1 leading-6 font-semibold text-white shadow-md hover:shadow-lg hover:bg-sky-800 cursor-pointer select-none">
        {functionName}
      </span>
    </>
  );
};
