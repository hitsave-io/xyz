import clsx from "clsx";
import * as React from "react";

import { Button } from "~/components/Button";
import { Container } from "~/components/Container";

import { CheckIcon } from "@heroicons/react/20/solid";

const { useState } = React;

interface Price {
  dollars?: number;
  text?: string;
  unit?: string;
}

interface Tier {
  featured: boolean;
  name: string;
  priceMonthly: Price;
  priceYearly: Price;
  description: string;
  href: string;
  buttonText: string;
  featureText: JSX.Element | string;
  includedFeatures: string[];
}

const tiers: Tier[] = [
  {
    featured: true,
    name: "Community",
    priceMonthly: { text: "Free beta" },
    priceYearly: { text: "Free beta" },
    description: "The free version of HitSave. Perfect for trying it out.",
    href: "#",
    buttonText: "Get Started",
    featureText: "What's included:",
    includedFeatures: [
      "One user",
      "100MB cloud cache",
      "7-day cloud cache history",
      "500 experiments",
      "Email support",
    ],
  },
  {
    featured: false,
    name: "Pro",
    priceMonthly: { text: "Coming soon" },
    priceYearly: { text: "Coming soon" },
    description: "Great for individuals and academics.",
    href: "#",
    buttonText: "Get Started",
    featureText: (
      <span>
        Everything in <strong>Community</strong>, plus:
      </span>
    ),
    includedFeatures: [
      "Up to 5 users",
      "5GB cloud cache per user",
      "Unlimited cloud cache history",
      "HitSave Time Travel",
      "Unlimited experiments",
    ],
  },
  {
    featured: false,
    name: "Team",
    priceMonthly: { text: "Coming soon" },
    priceYearly: { text: "Coming soon" },
    description: "The full-featured version of HitSave, for data teams.",
    href: "#",
    buttonText: "Get Started",
    featureText: (
      <span>
        Everything in <strong>Pro</strong>, plus:
      </span>
    ),
    includedFeatures: ["Up to 20 users", "10GB cloud cache per user"],
  },
  {
    featured: false,
    name: "Enterprise",
    priceMonthly: { text: "Coming soon" },
    priceYearly: { text: "Coming soon" },
    description: "For large organisations with bespoke requirements.",
    href: "#",
    buttonText: "Get Started",
    featureText: (
      <span>
        Everything in <strong>Team</strong>, plus:
      </span>
    ),
    includedFeatures: ["Private cloud deployment", "Priority support SLAs"],
  },
];

interface PriceProps {
  price: Price;
}

const Price: React.FC<PriceProps> = ({ price }) => {
  if (price.dollars) {
    return (
      <>
        <span className="text-4xl font-bold tracking-tight text-gray-900">
          ${price.dollars}
        </span>
        <span className="text-base font-medium text-gray-500">
          {price.unit}
        </span>
      </>
    );
  } else {
    return (
      <span className="text-2xl font-bold tracking-tight text-gray-900">
        {price.text}
      </span>
    );
  }
};

interface PricingProps {
  signInUrl: string;
}

export const Pricing: React.FC<PricingProps> = ({ signInUrl }) => {
  const [showYearly, setShowYearly] = useState(false);
  return (
    <section id="pricing" aria-label="Pricing" className="bg-white">
      <Container>
        <div className="w-full py-24 px-4 sm:px-6 lg:px-8">
          <div className="sm:align-center sm:flex sm:flex-col">
            <h1 className="text-5xl font-bold tracking-tight text-gray-900 sm:text-center">
              Pricing Plans
            </h1>
            <p className="mt-5 text-xl text-gray-500 sm:text-center">
              HitSave is currently in{" "}
              <strong className="text-brand">beta</strong>, and we're not
              charging for users to sample the current version free for small
              projects. <br />
              Let us know what you think!
            </p>
            {/*<div className="relative mt-6 flex self-center rounded-lg bg-gray-100 p-0.5 sm:mt-8">
              <button
                type="button"
                onClick={() => setShowYearly(false)}
                className={clsx(
                  showYearly
                    ? "relative ml-0.5 w-1/2 whitespace-nowrap rounded-md border border-transparent py-2 text-sm font-medium text-gray-700 focus:z-10 focus:outline-none sm:w-auto sm:px-8"
                    : "relative w-1/2 whitespace-nowrap rounded-md border-gray-200 bg-white py-2 text-sm font-medium text-gray-900 shadow-sm focus:z-10 focus:outline-none sm:w-auto sm:px-8"
                )}
              >
                Monthly billing
              </button>
              <button
                type="button"
                onClick={() => setShowYearly(true)}
                className={clsx(
                  !showYearly
                    ? "relative ml-0.5 w-1/2 whitespace-nowrap rounded-md border border-transparent py-2 text-sm font-medium text-gray-700 focus:z-10 focus:outline-none sm:w-auto sm:px-8"
                    : "relative w-1/2 whitespace-nowrap rounded-md border-gray-200 bg-white py-2 text-sm font-medium text-gray-900 shadow-sm focus:z-10 focus:outline-none sm:w-auto sm:px-8"
                )}
              >
                Yearly billing
              </button>
            </div>*/}
          </div>
          <div className="mt-12 space-y-4 sm:mt-16 sm:grid sm:grid-cols-2 sm:gap-6 sm:space-y-0 lg:mx-auto lg:max-w-4xl xl:mx-0 xl:max-w-none xl:grid-cols-4">
            {tiers.map((tier) => (
              <div
                key={tier.name}
                className={clsx(
                  tier.featured ? "border-brand bg-rose-50" : "border-gray-200",
                  "divide-y divide-gray-200 rounded-lg border shadow-sm"
                )}
              >
                <div className="p-6">
                  <h2 className="text-lg font-medium leading-6 text-gray-900">
                    {tier.name}
                  </h2>
                  <p className="mt-4 text-sm text-gray-500">
                    {tier.description}
                  </p>
                  <p className="mt-8">
                    <Price
                      price={showYearly ? tier.priceYearly : tier.priceMonthly}
                    />
                  </p>
                  <Button
                    href={signInUrl}
                    external
                    className={clsx(
                      tier.featured
                        ? "bg-brand border-brand hover:bg-red-500"
                        : "bg-gray-800 border-gray-800 hover:bg-gray-900",
                      "mt-8 block w-full rounded-md border py-2 text-center text-sm font-semibold text-white"
                    )}
                  >
                    {tier.buttonText}
                  </Button>
                </div>
                <div className="px-6 pt-6 pb-8">
                  <h3 className="text-sm font-medium text-gray-900">
                    {tier.featureText}
                  </h3>
                  <ul role="list" className="mt-6 space-y-4">
                    {tier.includedFeatures.map((feature) => (
                      <li key={feature} className="flex space-x-3">
                        <CheckIcon
                          className="h-5 w-5 flex-shrink-0 text-green-500"
                          aria-hidden="true"
                        />
                        <span className="text-sm text-gray-500">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
};
