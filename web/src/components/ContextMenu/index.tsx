import moment from "moment";
import * as React from "react";
import {
  ContextMenu as IContextMenu,
  ContextMenuValue as IContextMenuValue,
  ContextMenuKind,
  useUiState,
  Param,
} from "~/state/experiments";
import { Digest } from "../Digest";
import { Show } from "../visual";

interface ContextMenuProps {
  cxm: IContextMenu;
}

export const ContextMenu: React.FC<ContextMenuProps> = ({ cxm }) => {
  if (cxm.__kind__ === ContextMenuKind.Experiment) {
    return <ContextMenuExperiment />;
  } else if (cxm.__kind__ === ContextMenuKind.Param) {
    return <ContextMenuParam fn_digest={cxm.fn_digest} param={cxm.param} />;
  } else if (cxm.__kind__ === ContextMenuKind.Symbol) {
    return <ContextMenuSymbol name={cxm.symbol} />;
  } else if (cxm.__kind__ === ContextMenuKind.Value) {
    return <ContextMenuValue cxmVal={cxm} />;
  } else {
    return (
      <Frame>
        <h2 className="mb-4 font-mono font-medium text-xs">Getting Started</h2>
        <p>Here are some getting started tips!</p>
      </Frame>
    );
  }
};

interface ContextMenuParamProps {
  fn_digest: string;
  param: Param;
}

const ContextMenuParam: React.FC<ContextMenuParamProps> = ({ param }) => {
  return (
    <Frame>
      <Heading title={param.name} tag="Param" />
      {!!param.annotation && (
        <Group heading="Type">
          <Show o={param.annotation} />
        </Group>
      )}
    </Frame>
  );
};

interface ContextMenuValueProps {
  cxmVal: IContextMenuValue;
}

const ContextMenuValue: React.FC<ContextMenuValueProps> = ({ cxmVal }) => {
  return (
    <Frame>
      <Heading title="value" />
      <Group>
        <div className="font-mono">
          <Show o={cxmVal.val} detailed />
        </div>
      </Group>
    </Frame>
  );
};

interface ContextMenuExperimentProps {}

const ContextMenuExperiment: React.FC<ContextMenuExperimentProps> = () => {
  const uiState = useUiState((store) => store.ui);

  return (
    <Frame>
      <Heading title="Experiments" />
      <Group>
        <div className="flex flex-col items-start">
          {Object.keys(uiState.symbols).map((s) => (
            <div className="relative w-full flex items-center mb-1">
              <div className="flex h-3 items-center">
                <input
                  id={`symbol-${s}`}
                  checked={uiState.selectedSymbols.includes(s)}
                  onChange={() => {}}
                  aria-describedby="comments-description"
                  name={`symbol-${s}`}
                  type="checkbox"
                  className="h-3 w-3 rounded-sm border-gray-300 text-brand-600 text-sky-500 focus:ring-0 focus:ring-offset-0"
                />
              </div>
              <div className="ml-1">
                <label
                  htmlFor={`symbol-${s}`}
                  className="font-normal font-mono text-gray-700 leading-3"
                >
                  {s}
                </label>
                <span id="comments-description" className="text-gray-500">
                  <span className="sr-only">{s}</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </Group>
    </Frame>
  );
};

interface ContextMenuSymbolProps {
  name: string;
}

const ContextMenuSymbol: React.FC<ContextMenuSymbolProps> = ({ name }) => {
  const symbols = useUiState((store) => store.ui.symbols);
  const toggleSymbolVersion = useUiState((store) => store.toggleSymbolVersion);
  const toggleParam = useUiState((store) => store.toggleParam);
  const symbol = symbols[name];
  const versions = symbol.versions.sort((a, b) =>
    a.digest.localeCompare(b.digest)
  );
  const evaluationCount = symbol.versions.reduce(
    (acc, sv) => sv.experiments.length + acc,
    0
  );
  const lastEvaluationTime = symbol.versions
    .map((sv) => sv.experiments)
    .flat()
    .map((e) => Date.parse(e.start_time))[0];

  const params = symbol.versions.map((sv) => sv.params).flat();

  return (
    <Frame>
      <Heading title={name} tag="func" />
      <div className="flex flex-col">
        <Group heading="Evaluations">{evaluationCount}</Group>
        <Group heading="Last executed">
          {moment(lastEvaluationTime).format("DD-MMM-YYYY HH:mm:ss")}
        </Group>
        <Group heading="Versions">
          <div className="flex flex-col items-start">
            {versions.map((v) => (
              <div
                className="relative w-full flex items-center mb-1"
                key={v.digest}
              >
                <div className="flex h-3 items-center">
                  <input
                    id={`version-${v.digest}`}
                    checked={symbol.selectedVersions.includes(v.digest)}
                    onChange={() => toggleSymbolVersion(name, v.digest)}
                    aria-describedby="version-description"
                    name={`version-${v.digest}`}
                    type="checkbox"
                    className="h-3 w-3 rounded-sm border-gray-300 text-brand-600 text-sky-500 focus:ring-0 focus:ring-offset-0"
                  />
                </div>
                <div className="ml-1">
                  <label
                    htmlFor={`version-${v.digest}`}
                    className="font-normal font-mono text-gray-700 leading-3"
                  >
                    <Digest digest={v.digest} />
                  </label>
                  <span id="version-description" className="text-gray-500">
                    <span className="sr-only">
                      <Digest digest={v.digest} />
                    </span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Group>
        {/*<Group heading="Params">
          {params.map((param) => {
            const version = versions.find((v) =>
              v.params.map((p) => p.name).includes(param.name)
            );
            return (
              !!version && (
                <div
                  className="relative w-full flex items-center mb-1"
                  key={param.name}
                >
                  <div className="flex h-3 items-center">
                    <input
                      id={`param-${param.name}`}
                      checked={versions
                        .map((v) => v.selectedParams)
                        .flat()
                        .includes(param.name)}
                      onChange={() =>
                        toggleParam(symbol.name, version, param.name)
                      }
                      aria-describedby="version-description"
                      name={`param-${param.name}`}
                      type="checkbox"
                      className="h-3 w-3 rounded-sm border-gray-300 text-brand-600 text-sky-500 focus:ring-0 focus:ring-offset-0"
                    />
                  </div>
                  <div className="ml-1">
                    <label
                      htmlFor={`param-${param.name}`}
                      className="font-normal font-mono text-gray-700 leading-3"
                    >
                      {param.name}
                    </label>
                    <span id="param-description" className="text-gray-500">
                      <span className="sr-only">{param.name}</span>
                    </span>
                  </div>
                </div>
              )
            );
          })}
        </Group>*/}
      </div>
    </Frame>
  );
};

interface FrameProps {
  children: React.ReactNode;
}

const Frame: React.FC<FrameProps> = ({ children }) => {
  return <div className="w-full h-full flex flex-col">{children}</div>;
};

interface HeadingProps {
  title: string;
  tag?: string;
}

const Heading: React.FC<HeadingProps> = ({ title, tag }) => {
  return (
    <div className="flex">
      <h2 className="font-mono font-medium text-xs">{title}</h2>
      {!!tag && (
        <span className="ml-3 text-gray-400 uppercase relative top-1">
          {tag}
        </span>
      )}
    </div>
  );
};

interface GroupProps {
  heading?: string;
  children: React.ReactNode;
}

const Group: React.FC<GroupProps> = ({ heading, children }) => {
  return (
    <div className="mt-3">
      {!!heading && (
        <div className="w-full uppercase text-gray-400 mb-1">{heading}</div>
      )}
      {children}
    </div>
  );
};
