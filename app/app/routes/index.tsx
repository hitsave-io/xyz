import { Hero } from "~/components/landing/Hero";
import { Header } from "~/components/Header";
import hitsaveLogo from "~/images/hitsave_logo.svg";

import styles from "~/components/CodeAnim/styles.css";

export function links() {
  return [{ rel: "stylesheet", href: styles }];
}

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
  return (
    <>
      <Header />
      <main>
        <Hero />
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
