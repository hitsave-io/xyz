import * as React from "react";
import { Link } from "@remix-run/react";

interface NavLinkProps {
  href: string;
  external?: boolean;
  children?: React.ReactNode;
}

export const NavLink: React.FC<NavLinkProps> = ({
  href,
  external = false,
  children,
}) => {
  return external ? (
    <a
      href={href}
      className="inline-block rounded-lg py-1 px-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900"
    >
      {children}
    </a>
  ) : (
    <Link
      to={href}
      className="inline-block rounded-lg py-1 px-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900"
    >
      {children}
    </Link>
  );
};
