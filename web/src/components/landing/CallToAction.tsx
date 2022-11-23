import * as React from "react";
import { Button } from "~/components/Button";
import { Container } from "~/components/Container";
import backgroundImage from "~/images/background-call-to-action.jpg";

interface CallToActionProps {
  signInUrl: string;
}

export const CallToAction: React.FC<CallToActionProps> = ({ signInUrl }) => {
  return (
    <section
      id="get-started-today"
      className="relative overflow-hidden bg-blue-600 py-32"
    >
      <img
        className="absolute top-1/2 left-1/2 max-w-none -translate-x-1/2 -translate-y-1/2"
        src={backgroundImage}
        alt=""
        width={2347}
        height={1244}
      />
      <Container className="relative">
        <div className="mx-auto max-w-lg text-center">
          <h2 className="font-display text-3xl tracking-tight text-white sm:text-4xl md:text-5xl">
            Get started today
          </h2>
          <p className="mt-4 text-lg tracking-tight text-white">
            HitSave is in <strong>beta</strong>.
          </p>
          <p className="mt-4 text-lg tracking-tight text-white">
            Try the latest version by registering with your GitHub account.{" "}
            <a
              href="https://discord.gg/DfxGynVBcN"
              className="hover:decoration"
            >
              Join our Discord community
            </a>{" "}
            to ask questions and help guide the future of our project.
          </p>
          <div className="mt-10 flex items-center justify-center">
            <Button href={signInUrl} external color="brand">
              Get Started
            </Button>
            <Button
              external
              href="https://discord.gg/DfxGynVBcN"
              color="white"
              className="ml-4 text-slate-500 hover:text-brand"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="currentColor"
                className="h-4 w-4 mr-1 fill-slate-500 group-hover:fill-brand"
                viewBox="0 0 16 16"
              >
                <path d="M13.545 2.907a13.227 13.227 0 0 0-3.257-1.011.05.05 0 0 0-.052.025c-.141.25-.297.577-.406.833a12.19 12.19 0 0 0-3.658 0 8.258 8.258 0 0 0-.412-.833.051.051 0 0 0-.052-.025c-1.125.194-2.22.534-3.257 1.011a.041.041 0 0 0-.021.018C.356 6.024-.213 9.047.066 12.032c.001.014.01.028.021.037a13.276 13.276 0 0 0 3.995 2.02.05.05 0 0 0 .056-.019c.308-.42.582-.863.818-1.329a.05.05 0 0 0-.01-.059.051.051 0 0 0-.018-.011 8.875 8.875 0 0 1-1.248-.595.05.05 0 0 1-.02-.066.051.051 0 0 1 .015-.019c.084-.063.168-.129.248-.195a.05.05 0 0 1 .051-.007c2.619 1.196 5.454 1.196 8.041 0a.052.052 0 0 1 .053.007c.08.066.164.132.248.195a.051.051 0 0 1-.004.085 8.254 8.254 0 0 1-1.249.594.05.05 0 0 0-.03.03.052.052 0 0 0 .003.041c.24.465.515.909.817 1.329a.05.05 0 0 0 .056.019 13.235 13.235 0 0 0 4.001-2.02.049.049 0 0 0 .021-.037c.334-3.451-.559-6.449-2.366-9.106a.034.034 0 0 0-.02-.019Zm-8.198 7.307c-.789 0-1.438-.724-1.438-1.612 0-.889.637-1.613 1.438-1.613.807 0 1.45.73 1.438 1.613 0 .888-.637 1.612-1.438 1.612Zm5.316 0c-.788 0-1.438-.724-1.438-1.612 0-.889.637-1.613 1.438-1.613.807 0 1.451.73 1.438 1.613 0 .888-.631 1.612-1.438 1.612Z" />
              </svg>
              Discord
            </Button>
          </div>
        </div>
      </Container>
    </section>
  );
};
