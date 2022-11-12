import * as React from "react";
import { Form } from "@remix-run/react";
import clsx from "clsx";

import { Button } from "~/components/Button";
import { Container } from "~/components/Container";
import logoLaravel from "~/images/logos/laravel.svg";
import logoMirage from "~/images/logos/mirage.svg";
import logoStatamic from "~/images/logos/statamic.svg";
import logoStaticKit from "~/images/logos/statickit.svg";
import logoTransistor from "~/images/logos/transistor.svg";
import logoTuple from "~/images/logos/tuple.svg";
import hitsaveLogo from "~/images/hitsave_logo.svg";
import { CodeAnim } from "../CodeAnim";

const { useState } = React;

interface HeroProps {
  formData?: {
    message?: string;
    errors?: string[];
  };
  submitting?: boolean;
}

export const Hero: React.FC<HeroProps> = ({ formData }) => {
  const [waitlistIsOpen, setWaitlistIsOpen] = useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const onClick = () => {
    inputRef.current?.focus();
    setWaitlistIsOpen(true);
  };

  React.useEffect(() => {
    if (inputRef) {
      inputRef.current?.focus();
    }
  });

  const waitlist = formData?.message ? "message" : "button";

  return (
    <Container className="pt-20 pb-16 text-center lg:pt-32">
      <img className="mx-auto mb-4" src={hitsaveLogo} />
      <h1 className="mx-auto max-w-4xl font-mono text-lg font-bold tracking-tight text-slate-900">
        Instant caching for your data pipeline.
      </h1>
      <p className="mx-auto mt-6 max-w-2xl text-lg tracking-tight text-slate-700">
        Automatically and intelligently cache long running, computationally
        intensive or time consuming functions with a single import and a
        decorator.
      </p>
      {waitlist === "message" ? (
        <p className="my-10 h-10 flex justify-center items-center font-semibold text-brand">
          {formData?.message}
        </p>
      ) : (
        <>
          <div
            className={clsx(
              waitlistIsOpen && "hidden",
              "my-10 h-10 flex justify-center gap-x-6"
            )}
          >
            <Button color="blue" onClick={onClick}>
              Join Waitlist
            </Button>
          </div>
          <Form
            method="post"
            action="/?index"
            className={clsx(
              !waitlistIsOpen && "hidden",
              "mx-auto my-10 h-10 flex max-w-2xl text-sm font-medium text-gray-700"
            )}
          >
            <div className="mr-4 w-full border-b border-gray-300 focus-within:border-brand">
              <input
                ref={inputRef}
                name="email"
                type="text"
                className="block w-full h-full border-0 border-b border-transparent focus:border-brand focus:ring-0 font-normal text-center text-sm text-brand md:text-lg"
                placeholder="alan.turing@bletchley.com"
              />
              <div className="flex h-6 items-center text-red-600">
                {formData?.errors?.map((err) => (
                  <div className="justify-left">{err}</div>
                ))}
              </div>
            </div>
            <Button className=" h-full" type="submit" color="brand">
              Submit
            </Button>
          </Form>
        </>
      )}

      <div className="mx-auto mt-4 max-w-2xl text-lg md:text-xl">
        <CodeAnim />
      </div>
      <div className="mt-36 lg:mt-44">
        <p className="font-display text-base text-slate-900">
          Trusted by these companies so far
        </p>
        <ul
          role="list"
          className="mt-8 flex items-center justify-center gap-x-8 sm:flex-col sm:gap-x-0 sm:gap-y-10 xl:flex-row xl:gap-x-12 xl:gap-y-0"
        >
          {[
            [
              { name: "Transistor", logo: logoTransistor },
              { name: "Tuple", logo: logoTuple },
              { name: "StaticKit", logo: logoStaticKit },
            ],
            [
              { name: "Mirage", logo: logoMirage },
              { name: "Laravel", logo: logoLaravel },
              { name: "Statamic", logo: logoStatamic },
            ],
          ].map((group, groupIndex) => (
            <li key={groupIndex}>
              <ul
                role="list"
                className="flex flex-col items-center gap-y-8 sm:flex-row sm:gap-x-12 sm:gap-y-0"
              >
                {group.map((company) => (
                  <li key={company.name} className="flex">
                    <img src={company.logo} alt={company.name} />
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </div>
    </Container>
  );
};
