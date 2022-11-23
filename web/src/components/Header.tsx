import * as React from "react";
import { Link } from "@remix-run/react";
import { Popover, Transition } from "@headlessui/react";
import clsx from "clsx";

import { Button } from "~/components/Button";
import { Container } from "~/components/Container";
import { Logo } from "~/components/Logo";
import { NavLink } from "~/components/NavLink";
import { User } from "~/session.server";
import { ProfileDropdown } from "./ProfileDropdown";

const { Fragment } = React;

interface MobileNavLinkProps {
  href: string;
  external?: boolean;
  children?: React.ReactNode;
}

const MobileNavLink: React.FC<MobileNavLinkProps> = ({
  href,
  external = false,
  children,
}) => {
  return (
    <Popover.Button className="block w-full p-2">
      <NavLink href={href} external={external}>
        {children}
      </NavLink>
    </Popover.Button>
  );
};

function MobileNavIcon({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      className="h-3.5 w-3.5 overflow-visible stroke-slate-700"
      fill="none"
      strokeWidth={2}
      strokeLinecap="round"
    >
      <path
        d="M0 1H14M0 7H14M0 13H14"
        className={clsx(
          "origin-center transition",
          open && "scale-90 opacity-0"
        )}
      />
      <path
        d="M2 2L12 12M12 2L2 12"
        className={clsx(
          "origin-center transition",
          !open && "scale-90 opacity-0"
        )}
      />
    </svg>
  );
}

interface MobileNavigationProps {
  signInUrl: string;
  user?: User;
}

const MobileNavigation: React.FC<MobileNavigationProps> = ({
  signInUrl,
  user,
}) => {
  return (
    <Popover>
      <Popover.Button
        className="relative z-10 flex h-8 w-8 items-center justify-center [&:not(:focus-visible)]:focus:outline-none"
        aria-label="Toggle Navigation"
      >
        {({ open }) => <MobileNavIcon open={open} />}
      </Popover.Button>
      <Transition.Root>
        <Transition.Child
          as={Fragment}
          enter="duration-150 ease-out"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="duration-150 ease-in"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <Popover.Overlay className="fixed inset-0 bg-slate-300/50" />
        </Transition.Child>
        <Transition.Child
          as={Fragment}
          enter="duration-150 ease-out"
          enterFrom="opacity-0 scale-95"
          enterTo="opacity-100 scale-100"
          leave="duration-100 ease-in"
          leaveFrom="opacity-100 scale-100"
          leaveTo="opacity-0 scale-95"
        >
          <Popover.Panel
            as="div"
            className="absolute inset-x-0 top-full mt-4 flex origin-top flex-col rounded-2xl bg-white p-4 text-lg tracking-tight text-slate-900 shadow-xl ring-1 ring-slate-900/5"
          >
            <MobileNavLink href="#features">Why HitSave?</MobileNavLink>
            <MobileNavLink
              external
              href="https://docs.hitsave.io/guides/getting_started.html"
            >
              Getting Started
            </MobileNavLink>
            <MobileNavLink
              external
              href="https://docs.hitsave.io/guides/tutorials.html"
            >
              Tutorials
            </MobileNavLink>
            <MobileNavLink external href="https://docs.hitsave.io/">
              Docs
            </MobileNavLink>
            <MobileNavLink href="#pricing">Pricing</MobileNavLink>
            <hr className="m-2 border-slate-300/40" />
            {!user && (
              <MobileNavLink href={signInUrl} external>
                Sign in
              </MobileNavLink>
            )}
            {user && (
              <MobileNavLink href="/dashboard/experiments">
                Dashboard
              </MobileNavLink>
            )}
          </Popover.Panel>
        </Transition.Child>
      </Transition.Root>
    </Popover>
  );
};

interface HeaderProps {
  user: User | null;
  signInUrl: string;
}

export const Header: React.FC<HeaderProps> = ({ user, signInUrl }) => {
  return (
    <header className="py-10">
      <Container>
        <nav className="relative z-50 flex justify-between">
          <div className="flex items-center md:gap-x-12">
            <Link to="#" aria-label="Home">
              <Logo className="h-4 w-auto" />
            </Link>
            <div className="hidden md:flex lg:gap-x-6">
              <NavLink href="#features">Why HitSave?</NavLink>
              <NavLink
                external
                href="https://docs.hitsave.io/guides/getting_started.html"
              >
                Getting Started
              </NavLink>
              <NavLink
                external
                href="https://docs.hitsave.io/guides/tutorials.html"
              >
                Tutorials
              </NavLink>
              <NavLink external href="https://docs.hitsave.io/">
                Docs
              </NavLink>
              <NavLink href="#pricing">Pricing</NavLink>
            </div>
          </div>
          <div className="flex items-center gap-x-2 md:gap-x-3">
            {!user ? (
              <Button href={signInUrl} external color="brand">
                Get started
              </Button>
            ) : (
              <>
                <Button
                  className="hidden md:flex"
                  href="/dashboard/experiments"
                  color="brand"
                >
                  Dashboard
                </Button>
                <ProfileDropdown user={user} />
              </>
            )}
            <div className="-mr-1 md:hidden">
              <MobileNavigation signInUrl={signInUrl} user={user} />
            </div>
          </div>
        </nav>
      </Container>
    </header>
  );
};
