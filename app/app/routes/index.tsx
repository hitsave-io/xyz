import { useLoaderData } from "@remix-run/react";

import { Hero } from "~/components/landing/Hero";
import { Header } from "~/components/Header";
import hitsaveLogo from "~/images/hitsave_square.png";

import styles from "~/components/CodeAnim/styles.css";

export function links() {
  return [{ rel: "stylesheet", href: styles }];
}

export const loader = async ({ request }: { request: Request }) => {
  const url = new URL(request.url);
  const waitlistSuccess = url.searchParams.get("waitlistSuccess");
  if (waitlistSuccess === "true") {
    return true;
  } else if (waitlistSuccess === "false") {
    return false;
  } else {
    return null;
  }
};

export function meta() {
  return {
    title: "HitSave - Instant caching for your data pipeline.",
    "og:title": "HitSave - Instant caching for your data pipeline.",
    description:
      "Automatically and intelligently cache long running, computationally intensive or time consuming functions with a single import and a decorator.",
    "og:description":
      "Automatically and intelligently cache long running, computationally intensive or time consuming functions with a single import and a decorator.",
    "og:image:url": hitsaveLogo,
    "og:image:alt": "HitSave",
  };
}

export default function Home() {
  const waitlistSuccess = useLoaderData<typeof loader>();
  console.log(waitlistSuccess);
  return (
    <>
      <Header />
      <main>
        <Hero waitlistSuccess={waitlistSuccess} />
        {/*<PrimaryFeatures />
        <SecondaryFeatures />
        <CallToAction />
        <Testimonials />
        <Pricing />
        <Faqs />*/}
      </main>
      {/* <Footer /> */}
    </>
  );
}
