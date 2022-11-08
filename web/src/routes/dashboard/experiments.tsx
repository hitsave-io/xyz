import { LoaderFunction } from "@remix-run/node";
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

export const loader: LoaderFunction = async ({ request }) => {
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

export default function Experiments() {
  const experiments = useLoaderData<typeof loader>();
  const af = argsFreqs(experiments);
  const argList = Object.keys(af).sort((a, b) => {
    return af[b] - af[a];
  });

  return (
    <div className="py-6">
      <div className="mx-auto px-4 sm:px-6 md:px-8">
        <h1 className="text-2xl font-semibold text-gray-900">Experiments</h1>
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
                        fn_key
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        fn_hash
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        args_hash
                      </th>
                      {/*<th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        args
                      </th>*/}
                      {argList.map((arg) => (
                        <th
                          scope="col"
                          className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                          key={arg}
                        >
                          {arg}
                        </th>
                      ))}
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        content_hash
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        start_time
                      </th>
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        elapsed_process_time
                      </th>
                      <th
                        scope="col"
                        className="relative py-3.5 pl-3 pr-4 sm:pr-6 lg:pr-8"
                      >
                        <span className="sr-only">Edit</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {experiments.map((experiment) => (
                      <tr
                        key={`${experiment.fn_hash}${experiment.args_hash}${experiment.fn_key}`}
                      >
                        <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8">
                          {experiment.fn_key}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {experiment.fn_hash.slice(0, 10)}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {experiment.args_hash.slice(0, 10)}
                        </td>
                        {/*<td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          <ShowArgs args={experiment.args} />
                        </td>*/}
                        {argList.map((arg) => {
                          return (
                            <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                              {experiment.args[arg] ? (
                                <Show o={experiment.args[arg]} />
                              ) : (
                                <td></td>
                              )}
                            </td>
                          );
                        })}
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {experiment.content_hash.slice(0, 10)}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {experiment.start_time}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {experiment.elapsed_process_time}
                        </td>
                        <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6 lg:pr-8">
                          <a
                            href="#"
                            className="text-indigo-600 hover:text-indigo-900"
                          >
                            Edit
                            <span className="sr-only">
                              , {experiment.fn_key}
                            </span>
                          </a>
                        </td>
                      </tr>
                    ))}
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
