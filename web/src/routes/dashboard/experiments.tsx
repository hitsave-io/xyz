import { LoaderFunction } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { API } from "~/api";
import { Show, ShowArgs } from "../../components/visual";
import { getSession, redirectLogin } from "~/session.server";

/* Note on which time pretty-printing library to use:

[On the moment website][1] they say you should not use it for new projects.
So I (EWA) tried using [luxon][2], but they don't have good [duration pretty printing][3],
so I switched back to using moment. There is also time-ago but whatever.

[1]: https://momentjs.com/docs/#/-project-status/
[2]: https://moment.github.io/luxon/#/?id=luxon
[3]: https://github.com/moment/luxon/issues/1134

*/

import moment from 'moment'

function ppTimeAgo(isostring : string) {
  // luxon: return DateTime.fromISO(experiment.start_time).toRelative()
  return moment(isostring).fromNow()
}

function ppDuration(durationNanoseconds : number) {
  const durationSeconds = durationNanoseconds * 1e-9
  // luxon: return Duration.fromMillis( experiment.elapsed_process_time * 1e-6 ).toHuman()
  // alternative: humanize-duration https://github.com/EvanHahn/HumanizeDuration.js
  // moment: return moment.duration(durationMiliseconds).humanize()
  return `${durationSeconds.toPrecision(2)} seconds`
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
    return await res.json();
  }
};

export default function Experiments() {
  const experiments = useLoaderData<typeof loader>();
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
                      <th
                        scope="col"
                        className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900"
                      >
                        args
                      </th>
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
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          <ShowArgs args={experiment.args}/>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {experiment.content_hash.slice(0, 10)}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {ppTimeAgo(experiment.start_time)}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {ppDuration(experiment.elapsed_process_time)}
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
