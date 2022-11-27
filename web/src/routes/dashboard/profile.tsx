import { LoaderArgs } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { PaperClipIcon } from "@heroicons/react/20/solid";

import { getUser, redirectLogin } from "~/session.server";
import { registerPageload } from "~/db";

export const loader = async ({ request }: LoaderArgs) => {
  registerPageload(request);

  const user = await getUser(request);
  return user ?? redirectLogin(request.url);
};

export default function Profile() {
  const user = useLoaderData<typeof loader>();

  return (
    <div className="py-6">
      <div className="mx-auto px-4 sm:px-6 md:px-8">
        <h1 className="text-2xl font-semibold text-gray-900">User Profile</h1>
        <div className="py-5">
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Your account details.
          </p>
        </div>
        <div className="border-t border-gray-200 py-5">
          <dl className="flex flex-col gap-x-4 gap-y-8 sm:flex-row">
            <div>
              <img
                className="rounded-lg"
                width="200"
                src={user.gh_avatar_url}
              />
            </div>
            <div className="flex flex-col space-y-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Username</dt>
                <dd className="mt-1 text-sm text-gray-900">{user.gh_login}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">
                  Email address
                </dt>
                <dd className="mt-1 text-sm text-gray-900">{user.gh_email}</dd>
              </div>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
