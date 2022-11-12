import * as React from "react";
import { Link } from "@remix-run/react";
import clsx from "clsx";

interface NavLinkProps {
  href: string;
  className?: string;
  external?: boolean;
  children?: React.ReactNode;
}

export const NavLink: React.FC<NavLinkProps> = ({
  href,
  className = "",
  external = false,
  children,
}) => {
  return external ? (
    <a
      href={href}
      className={clsx(
        "inline-block rounded-lg py-1 px-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900",
        className
      )}
    >
      {children}
    </a>
  ) : (
    <Link
      to={href}
      className={clsx(
        "inline-block rounded-lg py-1 px-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900",
        className
      )}
    >
      {children}
    </Link>
  );
};
