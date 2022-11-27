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
import { SecondaryFeatures } from "~/components/landing/SecondaryFeatures";
import { CallToAction } from "~/components/landing/CallToAction";

export function links() {
  return [{ rel: "stylesheet", href: styles }];
}

export function meta() {
  return {
    title: "HitSave - Effortless data.",
    "og:title": "HitSave - Effortless data.",
    description:
      "Optimize your team's workflow with cloud memoization, experiment tracking and effortless data versioning.",
    "og:description":
      "Optimize your team's workflow with cloud memoization, experiment tracking and effortless data versioning.",
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
  const user = isPossiblyLoggedIn ? await getUser(request) : null;

  const params = {
    client_id: process.env.GH_CLIENT_ID || "",
    redirect_uri: `${process.env.HITSAVE_WEB_URL}/login`,
    scope: "user:email",
  };

  const signInUrl = `https://github.com/login/oauth/authorize?${new URLSearchParams(
    params
  ).toString()}`;

  return { user, signInUrl };
};

export default function Home() {
  const { user, signInUrl } = useLoaderData<typeof loader>();
  const formData = useActionData<typeof action>();

  return (
    <>
      <Header user={user} signInUrl={signInUrl} />
      <main>
        <Hero formData={formData} />
        <PrimaryFeatures />
        <SecondaryFeatures />
        <CallToAction signInUrl={signInUrl} />
        <Pricing signInUrl={signInUrl} />
        {/*<SecondaryFeatures />
        <CallToAction />
        <Testimonials />
        <Faqs />*/}
      </main>
      <Footer />
    </>
  );
}
