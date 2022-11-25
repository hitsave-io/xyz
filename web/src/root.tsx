import {
  ErrorBoundaryComponent,
  json,
  LinksFunction,
  MetaFunction,
} from "@remix-run/node";
import {
  Links,
  LiveReload,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useCatch,
  Link,
  useLoaderData,
} from "@remix-run/react";
import { createContext } from "react";

import styles from "./tailwind.css";

export const meta: MetaFunction = () => ({
  charset: "utf-8",
  title: "HitSave",
  viewport: "width=device-width,initial-scale=1",
});

export const links: LinksFunction = () => [
  { rel: "stylesheet", href: styles },
  {
    rel: "stylesheet",
    href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500;600;700&family=Lexend:wght@400;500;600;700&display=swap",
  },
];

interface AppContextProps {
  api_url: string;
}

export const AppContext = createContext<AppContextProps>({
  api_url: "https://api.hitsave.io",
});

export const loader = async () => {
  return json<AppContextProps>({
    api_url: process.env.HITSAVE_API_URL ?? "",
  });
};

export const unstable_shouldReload = () => false;

export default function App() {
  const env = useLoaderData<typeof loader>();
  return (
    <html lang="en" className="h-full bg-white">
      <head>
        <Meta />
        <Links />
      </head>
      <body className="h-full">
        <AppContext.Provider value={env}>
          <Outlet />
          <ScrollRestoration />
          <Scripts />
          <LiveReload />
        </AppContext.Provider>
      </body>
    </html>
  );
}

export const ErrorBoundary: ErrorBoundaryComponent = ({ error }) => {
  console.error(error);
  return (
    <html>
      <head>
        <title>Oh no!</title>
        <Meta />
        <Links />
      </head>
      <body>
        Oops. Something went wrong.
        <Scripts />
      </body>
    </html>
  );
};

// TODO: make this nice and pretty.
export function CatchBoundary() {
  const caught = useCatch();
  return (
    <html>
      <head>
        <title>Oops!</title>
        <Meta />
        <Links />
      </head>
      <body>
        <div className="min-h-full bg-white px-4 py-16 sm:px-6 sm:py-24 md:grid md:place-items-center lg:px-8">
          <div className="mx-auto max-w-max">
            <main className="sm:flex">
              <p className="text-4xl font-bold tracking-tight text-brand sm:text-5xl">
                {caught.status}
              </p>
              <div className="sm:ml-6">
                <div className="sm:border-l sm:border-gray-200 sm:pl-6">
                  <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
                    {caught.statusText}
                  </h1>
                  <p className="mt-1 text-base text-gray-500">
                    Please check the URL in the address bar and try again.
                  </p>
                </div>
                <div className="mt-10 flex space-x-3 sm:border-l sm:border-transparent sm:pl-6">
                  <Link
                    to="/"
                    className="inline-flex items-center rounded-md border border-transparent bg-brand px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  >
                    Go back home
                  </Link>
                  <a
                    href="#"
                    className="inline-flex items-center rounded-md border border-transparent bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  >
                    Contact support
                  </a>
                </div>
              </div>
            </main>
          </div>
        </div>
        <Scripts />
      </body>
    </html>
  );
}
