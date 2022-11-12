import clsx from "clsx";
import { useState } from "react";

import { Button } from "~/components/Button";
import { Container } from "~/components/Container";

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
    featured: false,
    name: "Community",
    priceMonthly: { text: "Free" },
    priceYearly: { text: "Free" },
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
    featured: true,
    name: "Pro",
    priceMonthly: { dollars: 50, unit: "/user /mo" },
    priceYearly: { dollars: 550, unit: "/user /yr" },
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
    priceMonthly: { dollars: 150, unit: "/user /mo" },
    priceYearly: { dollars: 150 * 11, unit: "/user /yr" },
    description: "The full-featured version of HitSave, for data teams.",
    href: "#",
    buttonText: "Try 14 days free",
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
    priceMonthly: { text: "Custom" },
    priceYearly: { text: "Custom" },
    description: "For large organisations with bespoke requirements.",
    href: "#",
    buttonText: "Contact us",
    featureText: (
      <span>
        Everything in <strong>Team</strong>, plus:
      </span>
    ),
    includedFeatures: ["Private cloud deployment", "Priority support SLAs"],
  },
];

function CheckIcon({ className }: { className: string }) {
  return (
    <svg
      aria-hidden="true"
      className={clsx(
        "h-6 w-6 flex-none fill-current stroke-current",
        className
      )}
    >
      <path
        d="M9.307 12.248a.75.75 0 1 0-1.114 1.004l1.114-1.004ZM11 15.25l-.557.502a.75.75 0 0 0 1.15-.043L11 15.25Zm4.844-5.041a.75.75 0 0 0-1.188-.918l1.188.918Zm-7.651 3.043 2.25 2.5 1.114-1.004-2.25-2.5-1.114 1.004Zm3.4 2.457 4.25-5.5-1.187-.918-4.25 5.5 1.188.918Z"
        strokeWidth={0}
      />
      <circle
        cx={12}
        cy={12}
        r={8.25}
        fill="none"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

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
      <span className="text-4xl font-bold tracking-tight text-gray-900">
        {price.text}
      </span>
    );
  }
};

export function Pricing() {
  const [showYearly, setShowYearly] = useState(false);
  return (
    <section id="pricing" aria-label="Pricing" className="bg-white">
      <Container>
        <div className="w-full py-24 px-4 sm:px-6 lg:px-8">
          <div className="sm:align-center sm:flex sm:flex-col">
            <h1 className="text-5xl font-bold tracking-tight text-gray-900 sm:text-center">
              Pricing Plans
            </h1>
            <p className="mt-5 text-xl text-gray-500 sm:text-center"></p>
            <div className="relative mt-6 flex self-center rounded-lg bg-gray-100 p-0.5 sm:mt-8">
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
            </div>
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
                    href={tier.href}
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
}
