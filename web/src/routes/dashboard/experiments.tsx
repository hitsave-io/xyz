import { LoaderArgs, LoaderFunction } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { API } from "~/api";
import { Show, ShowArgs, VisualObject } from "../../components/visual";
import { getSession, redirectLogin } from "~/session.server";

interface Experiment {
  fn_key: string;
  fn_hash: string;
  args: { [key: string]: VisualObject };
  args_hash: string;
  content_hash: string;
  is_experiment: boolean;
  start_time: string;
  elapsed_process_time: number;
  accesses: number;
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
import { ChevronDownIcon } from "@heroicons/react/24/outline";

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

const argsFreqs = (exps: Experiment[]): { [key: string]: number } => {
  const freqs: { [key: string]: number } = {};
  exps.forEach((exp) => {
    const args = exp.args;
    for (const key in args) {
      if (Object.hasOwnProperty.call(freqs, key)) {
        freqs[key] += 1;
      } else {
        freqs[key] = 1;
      }
    }
  });

  return freqs;
};

const parseFnKey = (fnKey: string): [string, string] => {
  const split = fnKey.split(":");
  if (split.length !== 2) {
    return [fnKey, ""];
  } else {
    return split as [string, string];
  }
};

export default function Experiments() {
  // TODO: need to figure out this TypeScript stuf..
  const experiments = useLoaderData<typeof loader>() as Experiment[];

  const af = argsFreqs(experiments);
  const argList = Object.keys(af).sort((a, b) => {
    return af[b] - af[a];
  });

  experiments.sort((a, b) => {
    return Date.parse(b.start_time) - Date.parse(a.start_time);
  });

  console.log(experiments);

  return (
    <div className="py-6">
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
          <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
            <div className="inline-block min-w-full py-2 align-middle">
              <div className="overflow-hidden shadow-sm ring-1 ring-black ring-opacity-5">
                <table className="min-w-full divide-y divide-gray-300">
                  <thead className="bg-gray-50">
                    <tr>
                      <th
                        scope="col"
                        className="px-3.5 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6 lg:pl-8"
                      >
                        Function
                      </th>
                      {argList.map((arg) => (
                        <th
                          scope="col"
                          className="px-3 py-3.5 text-center text-sm font-semibold font-mono text-blue-600"
                          key={arg}
                        >
                          {arg}
                        </th>
                      ))}
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        Returned (Digest)
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        <div className="group inline-flex">
                          Execution Start Time
                          <span className="ml-2 flex-none rounded bg-gray-200 text-gray-900 group-hover:bg-gray-300">
                            <ChevronDownIcon
                              className="h-5 w-5"
                              aria-hidden="true"
                            />
                          </span>
                        </div>
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        Execution Period
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        Function Digest
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        Arguments Digest
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {experiments.map((experiment) => {
                      const [module, functionName] = parseFnKey(
                        experiment.fn_key
                      );
                      return (
                        <tr
                          key={`${experiment.fn_hash}${experiment.args_hash}${experiment.fn_key}`}
                          className="hover:bg-gray-50 cursor-pointer"
                        >
                          <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8">
                            <FnKey
                              module={module}
                              functionName={functionName}
                            />
                          </td>
                          {argList.map((arg) => {
                            return (
                              <td
                                key={arg}
                                className="whitespace-nowrap px-3 py-4 text-sm text-gray-500 text-center"
                              >
                                {Object.hasOwnProperty.call(
                                  experiment.args,
                                  arg
                                ) ? (
                                  <Show o={experiment.args[arg]} />
                                ) : null}
                              </td>
                            );
                          })}
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                            {experiment.content_hash.slice(0, 10)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                            {ppTimeAgo(experiment.start_time)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                            {ppDuration(experiment.elapsed_process_time)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                            {experiment.fn_hash.slice(0, 10)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                            {experiment.args_hash.slice(0, 10)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

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
