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
    { name: "Settings", href: "#" },
    { name: "Sign out", href: "#" },
  ];

  return (
    <Menu as="div" className="relative ml-3">
      <div>
        <Menu.Button className="flex max-w-xs items-center rounded-full bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2">
          <span className="sr-only">Open user menu</span>
          <img
            className="h-8 w-8 rounded-full"
            src={user.gh_avatar_url}
            alt=""
          />
        </Menu.Button>
      </div>
      <Transition
        as={Fragment}
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <Menu.Items className="absolute right-0 z-20 mt-2 w-48 origin-top-right rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
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
