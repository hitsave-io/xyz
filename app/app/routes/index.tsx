import { useActionData, useTransition } from "@remix-run/react";
import { redirect, json, ActionArgs } from "@remix-run/node";
import validator from "validator";

import { Hero } from "~/components/landing/Hero";
import { PrimaryFeatures } from "~/components/landing/PrimaryFeatures";
import { Header } from "~/components/Header";
import hitsaveLogo from "~/images/hitsave_square.png";

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

export const action = async ({ request }: ActionArgs) => {
  const body = await request.formData();
  const email = body.get("email");

  if (!email) {
    return json({
      errors: ["Email address required"],
    });
  }

  if (!validator.isEmail(email)) {
    return json({
      errors: ["Invalid email address"],
    });
  }

  let res = await fetch("http://127.0.0.1:8080/waitlist", {
    method: "put",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
    }),
  });

  console.log(res.status);

  if (res.status == 200) {
    return json({
      message:
        "You have been added to our waitlist. Thank you for your interest - we'll be in touch soon!",
    });
  } else if (res.status == 409) {
    return json({
      message: "You're already on the waitlist! 🎉",
    });
  } else {
    return json({
      message: "Sorry - there was an error adding you to the waitlist. 😰",
    });
  }
};

export default function Home() {
  const formData = useActionData<typeof action>();
  const transition = useTransition();
  const submitting = transition.state === "submitting";

  return (
    <>
      <Header />
      <main>
        <Hero formData={formData} />
        <PrimaryFeatures />
        {/*<SecondaryFeatures />
        <CallToAction />
        <Testimonials />
        <Pricing />
        <Faqs />*/}
      </main>
      {/* <Footer /> */}
    </>
  );
}
