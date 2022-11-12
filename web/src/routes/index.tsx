import { useActionData, useLoaderData } from "@remix-run/react";
import { json, ActionArgs, LoaderArgs } from "@remix-run/node";
import validator from "validator";

import { Hero } from "~/components/landing/Hero";
import { PrimaryFeatures } from "~/components/landing/PrimaryFeatures";
import { Pricing } from "~/components/landing/Pricing";
import { Header } from "~/components/Header";
import hitsaveLogo from "~/images/hitsave_square.png";
import { API } from "~/api";

import styles from "~/components/CodeAnim/styles.css";
import { getUser, hasUnexpiredJwt } from "~/session.server";
import { Footer } from "~/components/Footer";

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

  if (!validator.isEmail(email.toString())) {
    return json({
      errors: ["Invalid email address"],
    });
  }

  let res = await API.fetch("/waitlist", {
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

export const loader = async ({ request }: LoaderArgs) => {
  // Although they may have an unexpired JWT, this JWT might for some reason
  // still be invalid. We will leave this to the API itself to validate. This is
  // just a hint.
  const isPossiblyLoggedIn = hasUnexpiredJwt(request);
  if (isPossiblyLoggedIn) {
    return await getUser(request);
  } else {
    return null;
  }
};

export default function Home() {
  const user = useLoaderData<typeof loader>();
  const formData = useActionData<typeof action>();

  return (
    <>
      <Header user={user} />
      <main>
        <Hero formData={formData} />
        <PrimaryFeatures />
        <Pricing />
        {/*<SecondaryFeatures />
        <CallToAction />
        <Testimonials />
        <Faqs />*/}
      </main>
      <Footer />
    </>
  );
}
