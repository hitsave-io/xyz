import * as React from "react";
import { Dialog, Transition } from "@headlessui/react";
import {
  Bars3Icon,
  BeakerIcon,
  FolderIcon,
  UsersIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import clsx from "clsx";

import { ProfileDropdown } from "~/components/ProfileDropdown";
import { User } from "~/session.server";

const { Fragment, useState } = React;

interface AppShellProps {
  user: User;
  onClickTitle?: React.MouseEventHandler;
  children?: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  user,
  onClickTitle = () => {},
  children,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigation = [
    {
      name: "Projects",
      href: "/dashboard/projects",
      icon: FolderIcon,
      current: false,
    },
    {
      name: "Experiments",
      href: "/dashboard/experiments",
      icon: BeakerIcon,
    },
    {
      name: "Team",
      href: "/dashboard/team",
      icon: UsersIcon,
      current: false,
    },
  ];

  return (
    <div className="h-full">
      <Transition.Root show={sidebarOpen} as={Fragment}>
        <Dialog
          as="div"
          className="relative z-40 md:hidden"
          onClose={setSidebarOpen}
        >
          <Transition.Child
            as={Fragment}
            enter="transition-opacity ease-linear duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="transition-opacity ease-linear duration-300"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-gray-600 bg-opacity-75" />
          </Transition.Child>

          <div className="fixed inset-0 z-40 flex">
            <Transition.Child
              as={Fragment}
              enter="transition ease-in-out duration-300 transform"
              enterFrom="-translate-x-full"
              enterTo="translate-x-0"
              leave="transition ease-in-out duration-300 transform"
              leaveFrom="translate-x-0"
              leaveTo="-translate-x-full"
            >
              <Dialog.Panel className="relative flex w-full max-w-xs flex-1 flex-col bg-white pt-5 pb-4">
                <Transition.Child
                  as={Fragment}
                  enter="ease-in-out duration-300"
                  enterFrom="opacity-0"
                  enterTo="opacity-100"
                  leave="ease-in-out duration-300"
                  leaveFrom="opacity-100"
                  leaveTo="opacity-0"
                >
                  <div className="absolute top-0 right-0 -mr-12 pt-2">
                    <button
                      type="button"
                      className="ml-1 flex h-10 w-10 items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
                      onClick={() => setSidebarOpen(false)}
                    >
                      <span className="sr-only">Close sidebar</span>
                      <XMarkIcon
                        className="h-6 w-6 text-white"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </Transition.Child>
                <div className="mt-5 h-0 flex-1 overflow-y-auto">
                  <nav className="space-y-1 px-2">
                    {navigation.map((item) => (
                      <a
                        key={item.name}
                        href={item.href}
                        title={item.name}
                        className={clsx(
                          item.current && "bg-gray-100 text-gray-900",
                          !item.current &&
                            "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                          "group flex items-center px-2 py-2 text-base font-medium rounded-md"
                        )}
                      >
                        <item.icon
                          className={clsx(
                            item.current && "text-gray-500",
                            !item.current &&
                              "text-gray-400 group-hover:text-gray-500",
                            "mr-4 flex-shrink-0 h-6 w-6"
                          )}
                          aria-hidden="true"
                        />
                        {item.name}
                      </a>
                    ))}
                    <div className="relative">
                      <div
                        className="absolute inset-x-6 inset-y-2 flex items-center"
                        aria-hidden="true"
                      >
                        <div className="w-full border-t border-gray-300" />
                      </div>
                    </div>
                  </nav>
                </div>
              </Dialog.Panel>
            </Transition.Child>
            <div className="w-12 flex-shrink-0" aria-hidden="true">
              {/* Dummy element to force sidebar to shrink to fit close icon */}
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Static sidebar for desktop */}
      <div className="hidden md:fixed md:inset-y-0 md:flex md:w-12 md:flex-col">
        {/* Sidebar component */}
        <div className="flex flex-grow flex-col overflow-y-auto bg-midnight pt-2 pb-2">
          <div className="flex flex-grow flex-col">
            <nav className="flex-1 space-y-1 pb-4">
              {navigation.map((item) => (
                <a
                  key={item.name}
                  href={item.href}
                  title={item.name}
                  className={clsx(
                    item.current && "bg-gray-100 text-gray-900",
                    !item.current && "text-white hover:bg-brand",
                    "group flex items-center justify-center w-12 h-12 text-sm font-medium"
                  )}
                >
                  <item.icon
                    className="flex-shrink-0 h-6 w-6 text-white"
                    aria-hidden="true"
                  />
                </a>
              ))}
            </nav>
            <div className="flex flex-1"></div>
            <div className="flex items-center">
              <ProfileDropdown user={user} />
            </div>
          </div>
        </div>
      </div>

      {/* Title bar */}
      <div className="flex flex-1 flex-col md:pl-12 h-full">
        <div
          className="flex items-center px-0 md:px-3 h-16 flex-shrink-0 bg-white border-b border-solid border-gray-100"
          onClick={onClickTitle}
        >
          <button
            type="button"
            className="px-4 h-full text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 md:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <span className="sr-only">Open sidebar</span>
            <Bars3Icon className="h-6 w-6" aria-hidden="true" />
          </button>
          <h1 className="text-2xl font-semibold text-gray-900">Experiments</h1>
        </div>

        {/* Main content */}
        <main className="flex-1 overflow-y-hidden">{children}</main>
      </div>
    </div>
  );
};
