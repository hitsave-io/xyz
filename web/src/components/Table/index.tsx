import * as React from "react";
import { useState } from "react";
import {
  ArrowLongDownIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  EllipsisHorizontalIcon,
} from "@heroicons/react/24/outline";
import clsx from "clsx";

import { Show } from "~/components/visual";
import {
  Experiment,
  Arg,
  useUiState,
  ContextMenuKind,
  SymbolVersion,
} from "~/state/experiments";
import { Digest } from "../Digest";

interface TableProps {
  symbol: string;
  version: SymbolVersion;
}

function getArgs(exp: Experiment): Arg[] {
  return exp.args;
}

export const Table: React.FC<TableProps> = ({ symbol, version }) => {
  const [open, setOpen] = useState(false);
  const [modulePath, symbolPath] = symbol.split(":");

  const setContextMenu = useUiState((store) => store.setContextMenu);

  return (
    <div
      className={clsx(
        open && "border-b",
        "inline-block min-w-full border-gray-300 bg-gray-100"
      )}
      key={symbol}
      onClick={() => {
        setContextMenu({
          __kind__: ContextMenuKind.Symbol,
          symbol,
        });
      }}
    >
      <div
        className="group h-8 top-0 z-10 border-b border-collapse border-gray-300 bg-white pl-3 pr-1 text-xs text-left font-semibold text-gray-900 font-mono cursor-pointer flex items-center select-none"
        onClick={() => {
          setOpen((o) => !o);
        }}
      >
        <div
          className={clsx(
            "w-3 mr-2 transition-transform text-gray-400 group-hover:text-brand",
            open && "rotate-90"
          )}
          style={{ minWidth: `${3 / 4}rem` }}
        >
          <ChevronRightIcon strokeWidth="3" />
        </div>
        <span
          className={clsx(
            "group-hover:text-brand",
            open ? "text-brand" : "text-gray-600"
          )}
        >
          {modulePath}
        </span>
        <span
          className={clsx(
            "group-hover:text-brand",
            open ? "text-brand" : "text-gray-600"
          )}
        >
          &nbsp;:&nbsp;
        </span>
        <span
          className={clsx(
            "group-hover:text-brand",
            open ? "text-brand" : "text-gray-600"
          )}
        >
          {symbolPath}
        </span>
        <span className="font-normal ml-2 text-xxs text-gray-300 group-hover:text-gray-400 relative top-1">
          <Digest digest={version.digest} />
        </span>
        <div className="flex-1"></div>
        <div
          className={clsx(
            open ? "block" : "hidden",
            "w-5 h-5 p-1 ml-1 text-gray-400 bg-white rounded hover:!bg-gray-50 hover:!text-brand"
          )}
        >
          <ArrowPathIcon title="Refresh" />
        </div>
        <div
          className={clsx(
            open ? "block" : "hidden",
            "w-5 h-5 p-1 ml-1 text-gray-400 bg-white rounded group-hover:block hover:!bg-gray-50 hover:!text-brand"
          )}
        >
          <EllipsisHorizontalIcon />
        </div>
      </div>
      {open && (
        <table className="table-fixed">
          <thead>
            <tr>
              {version.params.map((param) => (
                <HeaderCell
                  name={param.name}
                  key={param.name}
                  tag="Param"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!!param) {
                      return setContextMenu({
                        __kind__: ContextMenuKind.Param,
                        fn_digest: version.digest,
                        param,
                      });
                    }
                  }}
                />
              ))}
              <HeaderCell name="returns" tag="Ret" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-300 bg-white">
            {version.experiments.map((experiment) => {
              return (
                <tr
                  className="divide-x divide-gray-300 border-r border-gray-300"
                  key={`${experiment.fn_hash}${experiment.args_hash}${experiment.fn_key}`}
                >
                  {version.params.map((param) => {
                    const val = experiment.args.find(
                      (arg) => arg.name === param.name
                    )?.value;

                    return (
                      <TableCell
                        name={param.name}
                        key={param.name}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!!val) {
                            return setContextMenu({
                              __kind__: ContextMenuKind.Value,
                              fn_digest: version.digest,
                              args_digest: experiment.args_hash,
                              val,
                            });
                          }
                        }}
                      >
                        {!!val && <Show o={val} />}
                      </TableCell>
                    );
                  })}
                  <TableCell
                    name="res"
                    onClick={(e) => {
                      e.stopPropagation();
                      return setContextMenu({
                        __kind__: ContextMenuKind.Value,
                        fn_digest: version.digest,
                        args_digest: experiment.args_hash,
                        val: experiment.result_json,
                      });
                    }}
                  >
                    <Show o={experiment.result_json} />
                  </TableCell>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

interface HeaderCellProps {
  name: string;
  tag?: string;
  onClick?: React.MouseEventHandler<HTMLElement>;
}

const HeaderCell: React.FC<HeaderCellProps> = ({ name, tag, onClick }) => {
  return (
    <th
      scope="col"
      className="group sticky top-0 w-48 h-6 z-10 p-0 border-b border-r border-gray-300 bg-gray-100 hover:bg-blue-50 text-gray-600 text-center text-xs font-medium font-mono whitespace-nowrap cursor-pointer"
      onClick={onClick}
    >
      <div className="flex h-full items-center pr-1">
        <div className="flex flex-col space-y-px m-px mr-2">
          <div className="w-2.5 h-2.5 bg-gray-200 hover:bg-gray-400 cursor:pointer"></div>
          <div className="w-2.5 h-2.5 bg-gray-200 hover:bg-gray-400 cursor:pointer"></div>
        </div>
        <span className="truncate text-gray-500 group-hover:text-gray-600">
          {name}
        </span>
        <div className="flex-1"></div>
        {!!tag && (
          <div className="uppercase font-normal ml-2 text-xxs text-gray-300 group-hover:text-gray-400 relative top-1">
            {tag}
          </div>
        )}
        <div className="w-4 text-sky-300 group-hover:text-sky-400 hover:!text-sky-500">
          <ArrowLongDownIcon />
        </div>
      </div>
    </th>
  );
};

interface TableCellProps {
  name: string;
  children?: React.ReactNode;
  onClick?: React.MouseEventHandler<HTMLElement>;
}

const TableCell: React.FC<TableCellProps> = ({ name, onClick, children }) => {
  return (
    <td
      key={name}
      className="w-48 h-6 p-0 font-mono text-xs text-gray-500 truncate bg-white hover:bg-gray-50 cursor-pointer"
      onClick={onClick}
    >
      <div
        className="pl-5 truncate"
        style={{ maxWidth: `${12 * 16 - 2}px`, minWidth: `${12 * 16 - 2}px` }}
      >
        {children}
      </div>
    </td>
  );
};
