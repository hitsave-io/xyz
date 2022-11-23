import { useId } from "react";
import { Tab } from "@headlessui/react";
import clsx from "clsx";
import {
  LightBulbIcon,
  UserGroupIcon,
  CircleStackIcon,
} from "@heroicons/react/24/solid";

import { Container } from "~/components/Container";
import screenshotContacts from "~/images/screenshots/contacts.png";
import screenshotInventory from "~/images/screenshots/inventory.png";
import screenshotProfitLoss from "~/images/screenshots/profit-loss.png";

const features = [
  {
    name: "Simple",
    summary: "You write functions; we don't make any other assumptions.",
    description:
      "HitSave is perfect for any field: machine learning, statistics, bioinformatics, finance, vision, optimisation, business analytics... anything involving data.",
    image: screenshotContacts,
    icon: function ContactsIcon() {
      return <LightBulbIcon className="p-2 text-white" />;
    },
  },
  {
    name: "Collaborative",
    summary: "Share memoized results with your team.",
    description:
      "Collaborate and modify code without fear of consuming stale data or overwriting key results. Model weights, datasets, logs are instantly available to downstream projects.",
    image: screenshotProfitLoss,
    icon: function ReportingIcon() {
      let id = useId();
      return <UserGroupIcon className="p-2 text-white" />;
    },
  },
  {
    name: "Datasets",
    summary: "Fuss-free dataset catalogues.",
    description:
      "Snaphot and upload your datasets, managed in a content-addressed cloud store. Keep track of licencing, compliance and auditing. Stream public datasets directly from our catalogue.",
    image: screenshotInventory,
    icon: function InventoryIcon() {
      return <CircleStackIcon className="p-2 text-white" />;
    },
  },
];

function Feature({ feature, isActive, className, ...props }) {
  return (
    <div
      className={clsx(className, !isActive && "opacity-75 hover:opacity-100")}
      {...props}
    >
      <div
        className={clsx(
          "w-9 rounded-lg",
          isActive ? "bg-blue-600" : "bg-slate-500"
        )}
      >
        <svg aria-hidden="true" className="h-9 w-9 p-1.5" fill="none">
          <feature.icon />
        </svg>
      </div>
      <h3
        className={clsx(
          "mt-6 text-sm font-medium",
          isActive ? "text-blue-600" : "text-slate-600"
        )}
      >
        {feature.name}
      </h3>
      <p className="mt-2 font-display text-xl text-slate-900">
        {feature.summary}
      </p>
      <p className="mt-4 text-sm text-slate-600">{feature.description}</p>
    </div>
  );
}

function FeaturesMobile() {
  return (
    <div className="-mx-4 mt-20 flex flex-col gap-y-10 overflow-hidden px-4 sm:-mx-6 sm:px-6 lg:hidden">
      {features.map((feature) => (
        <div key={feature.name}>
          <Feature feature={feature} className="mx-auto max-w-2xl" isActive />
          {/*<div className="relative mt-10 pb-10">
            <div className="absolute -inset-x-4 bottom-0 top-8 bg-slate-200 sm:-inset-x-6" />
            <div className="relative mx-auto w-[52.75rem] overflow-hidden rounded-xl bg-white shadow-lg shadow-slate-900/5 ring-1 ring-slate-500/10">
              <img
                className="w-full"
                src={feature.image}
                alt=""
                sizes="52.75rem"
              />
            </div>
          </div>*/}
        </div>
      ))}
    </div>
  );
}

function FeaturesDesktop() {
  return (
    <Tab.Group as="div" className="hidden lg:mt-20 lg:block">
      {({ selectedIndex }) => (
        <>
          <Tab.List className="grid grid-cols-3 gap-x-8">
            {features.map((feature, featureIndex) => (
              <Feature
                key={feature.name}
                feature={{
                  ...feature,
                  name: (
                    <Tab className="[&:not(:focus-visible)]:focus:outline-none">
                      <span className="absolute inset-0" />
                      {feature.name}
                    </Tab>
                  ),
                }}
                isActive={featureIndex === selectedIndex}
                className="relative"
              />
            ))}
          </Tab.List>
          {/*<Tab.Panels className="relative mt-20 overflow-hidden rounded-4xl bg-slate-200 px-14 py-16 xl:px-16">
            <div className="-mx-5 flex">
              {features.map((feature, featureIndex) => (
                <Tab.Panel
                  static
                  key={feature.name}
                  className={clsx(
                    "px-5 transition duration-500 ease-in-out [&:not(:focus-visible)]:focus:outline-none",
                    featureIndex !== selectedIndex && "opacity-60"
                  )}
                  style={{ transform: `translateX(-${selectedIndex * 100}%)` }}
                  aria-hidden={featureIndex !== selectedIndex}
                >
                  <div className="w-[52.75rem] overflow-hidden rounded-xl bg-white shadow-lg shadow-slate-900/5 ring-1 ring-slate-500/10">
                    <img
                      className="w-full"
                      src={feature.image}
                      alt=""
                      sizes="52.75rem"
                    />
                  </div>
                </Tab.Panel>
              ))}
            </div>
            <div className="pointer-events-none absolute inset-0 rounded-4xl ring-1 ring-inset ring-slate-900/10" />
          </Tab.Panels>*/}
        </>
      )}
    </Tab.Group>
  );
}

export function SecondaryFeatures() {
  return (
    <section
      id="secondary-features"
      aria-label="Simple. Collaborative. Data."
      className="pt-20 pb-14 sm:pb-20 sm:pt-32 lg:pb-32"
    >
      <Container>
        <div className="mx-auto max-w-2xl md:text-center">
          <h2 className="font-display text-3xl tracking-tight text-slate-900 sm:text-4xl md:text-5xl">
            Simple. Collaborative. Data.
          </h2>
        </div>
        <FeaturesMobile />
        <FeaturesDesktop />
      </Container>
    </section>
  );
}
