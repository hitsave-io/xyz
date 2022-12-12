import * as React from "react";
import { Menu, Transition } from "@headlessui/react";
import { User } from "~/session.server";
import clsx from "clsx";

const { Fragment } = React;

interface ProfileDropdownProps {
  user: User;
}

export const ProfileDropdown: React.FC<ProfileDropdownProps> = ({ user }) => {
  const userNavigation = [
    {
      name: (
        <span>
          Signed in as <strong>{user.gh_login}</strong>
        </span>
      ),
      href: "/dashboard/profile",
    },
    // { name: "Settings", href: "#" },
    { name: "Sign out", href: "#" },
  ];

  return (
    <Menu as="div" className="w-full flex max-w-ws items-center justify-center">
      <Menu.Button className="rounded-full text-sm ring-1 ring-white focus:ring-1 focus:ring-brand">
        <img
          className="h-7 w-7 rounded-full"
          src={user.gh_avatar_url}
          alt={user.gh_login}
        />
      </Menu.Button>
      <Transition
        as={Fragment}
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <Menu.Items className="absolute left-2 bottom-16 z-20 mt-2 w-48 origin-bottom-left rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
          {userNavigation.map((item) => (
            <Menu.Item key={item.name.toString()}>
              {({ active }) => (
                <a
                  href={item.href}
                  className={clsx(
                    active && "bg-gray-100",
                    "block px-4 py-2 text-sm text-gray-700"
                  )}
                >
                  {item.name}
                </a>
              )}
            </Menu.Item>
          ))}
        </Menu.Items>
      </Transition>
    </Menu>
  );
};
