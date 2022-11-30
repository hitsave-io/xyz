// State for the experiment dashboard.

import create from "zustand";
import { devtools, persist } from "zustand/middleware";
import { VisualObject } from "~/components/visual";

export interface UiState {
  selectedSymbols: string[];
  contextMenu: ContextMenu;

  // *All* symbols loaded in the UI. Not just the ones which are selected
  // above.
  symbols: { [key: string]: Symbol };
}

export interface Experiment {
  fn_key: string;
  fn_hash: string;
  args: Arg[];
  args_hash: string;
  result_json: VisualObject;
  content_hash: string;
  is_experiment: boolean;
  start_time: string;
  elapsed_process_time: number;
  accesses: number;
}

// As per `inspect._ParameterKind`.
export enum ParameterKind {
  PositionalOnly = 0,
  PositionalOrKeyword = 1,
  VarPositional = 2,
  KeywordOnly = 3,
  VarKeyword = 4,
}

export interface Arg {
  name: string;
  value: VisualObject;
  is_default?: boolean;
  annotation?: VisualObject;
  kind?: ParameterKind;
  docs?: string;
}

export interface Param {
  name: string;
  annotation?: VisualObject;
  kind?: ParameterKind;
  docs?: string;
}

export interface Symbol {
  name: string;

  selectedVersions: string[];

  // Array of *all* version loaded in the UI. Not just the ones which are
  // selected above.
  versions: SymbolVersion[];
}

export interface SymbolVersion {
  digest: string;

  selectedParams: string[];

  // Maps arg names to `ColumnLayout`s. This is not guaranteed to contain
  // matching keys for each arg. If an arg doesn't appear in this map, then its
  // column should be rendered with defaults.
  columns: { [key: string]: ColumnLayout };

  // Array of *all* params belonging to this symbol-version. Not just the ones
  // which are currently selected above.
  params: Param[];

  // List of all the experiments which belong to this symbol version.
  experiments: Experiment[];
}

export interface ColumnLayout {
  // * `default`: a fixed-width column. This renders with text-ellipsis whenever
  //    anything overflows, and never has text wrap.
  // * `max-content`: expands the column to ensure that the largest content
  //    appearing anywhere in the column is fully visible
  // * `min-content`: collapses the column to be smaller than the default if
  //    the content of each row is small enough
  // * `wrap`: allows row height to vary, wrapping contained text
  width: "default" | "max-content" | "min-content" | "wrap";

  // Determines whether this column should render objects like images and plotly
  // plots inline, or just display a simple text hint.
  //
  // default: false
  inlineObjects: boolean;

  // todo: sorting stuff goes here. it should store sort options for this column
  // which are based on the data type of the arg. the sort options on this
  // object may or may not actually be in use. the `SymbolVersion` which
  // contains this object will have a field which determines which arg is
  // actually driving row ordering at any given moment.
}

export enum ContextMenuKind {
  // The user has just clicked on the page heading. We display a list of
  // available symbols. They can click select these with checkboxes to have
  // them appear as tables.
  Experiment = 1,

  // The user has just clicked on a table drawer (the white bar across the
  // top of a table, which allows it to be expanded and collapsed). We display
  // information like: how many experiments there are with this symbol, last
  // execution time, args list for selections (default all ticked), return
  // values for selections (default all ticked).
  Symbol = 2,

  // The user has just clicked on an arg. We display information about the arg,
  // like its name & type. We also provide options for display (sorting,
  // filtering).
  Param = 3,

  // The user has just clicked on a Python value in one of the table cells.
  // We display things like its digest (with a copy button), its value, a
  // detail inspector (so if its an image, we can see it larger).
  Value = 4,
}

export interface ContextMenuExperiment {
  __kind__: ContextMenuKind.Experiment;
}

export interface ContextMenuSymbol {
  __kind__: ContextMenuKind.Symbol;

  // Which symbol this context menu is displaying.
  symbol: string;
}

export interface ContextMenuParam {
  __kind__: ContextMenuKind.Param;

  // Which fn_digest (i.e. which table), is this arg a part of.
  fn_digest: string;

  param: Param;
}

export interface ContextMenuValue {
  __kind__: ContextMenuKind.Value;

  // Which fn_digest (i.e. which table), is this value from.
  fn_digest: string;

  // In conjunction with fn_digest, uniquely identifies the specific
  // evaluation this value is from.
  args_digest: string;

  // The visual object for displaying this value.
  val: VisualObject;
}

export type ContextMenu =
  | ContextMenuExperiment
  | ContextMenuSymbol
  | ContextMenuParam
  | ContextMenuValue;

interface UiStore {
  ui: UiState;
  fromExps: (exp: Experiment[]) => void;
  setContextMenu: (cxm: ContextMenu) => void;
  toggleSymbolVersion: (symbol: string, version: string) => void;
  toggleParam: (
    symbolName: string,
    version: SymbolVersion,
    paramName: string
  ) => void;
}

export const useUiState = create<UiStore>()(
  devtools(
    persist((set) => ({
      ui: blankState(),
      fromExps: (exps) =>
        set((prev) => ({ ...prev, ui: fromExperimentList(exps) })),
      setContextMenu: (cxm) =>
        set((prev) => ({
          ...prev,
          ui: { ...prev.ui, contextMenu: cxm },
        })),
      toggleSymbolVersion: (symbol: string, version: string) => {
        set((prev) => ({
          ...prev,
          ui: {
            ...prev.ui,
            symbols: {
              ...prev.ui.symbols,
              [symbol]: {
                ...prev.ui.symbols[symbol],
                selectedVersions: toggleStringInArray(
                  prev.ui.symbols[symbol].selectedVersions,
                  version
                ),
              },
            },
          },
        }));
      },
      toggleParam: (
        symbolName: string,
        version: SymbolVersion,
        paramName: string
      ) => {
        set((prev) => ({
          ...prev,
          ui: {
            ...prev.ui,
            symbols: {
              ...prev.ui.symbols,
              [symbolName]: {
                ...prev.ui.symbols[symbolName],
                versions: prev.ui.symbols[symbolName].versions.map((v) => {
                  if (v.digest === version.digest) {
                    return {
                      ...v,
                      selectedParams: toggleStringInArray(
                        v.selectedParams,
                        paramName
                      ),
                    };
                  } else {
                    return v;
                  }
                }),
              },
            },
          },
        }));
      },
    }))
  )
);

// Used when toggling selection state with checkboxes.
function toggleStringInArray(arr: string[], s: string): string[] {
  const idx = arr.indexOf(s);
  if (idx === -1) {
    return [...arr, s];
  } else {
    return [...arr.slice(0, idx), ...arr.slice(idx + 1, arr.length)];
  }
}

export function blankState(): UiState {
  return {
    selectedSymbols: [],
    contextMenu: { __kind__: ContextMenuKind.Experiment },
    symbols: {},
  };
}

function fromExperimentList(exps: Experiment[]): UiState {
  const symbols: { [key: string]: Symbol } = {};

  for (const exp of exps) {
    if (!symbols.hasOwnProperty(exp.fn_key)) {
      symbols[exp.fn_key] = newSymbol(exp.fn_key, [exp.fn_hash]);
    }

    const symbol = symbols[exp.fn_key];
    let symbolVersion = symbol.versions.find((v) => v.digest === exp.fn_hash);

    if (!symbolVersion) {
      symbolVersion = newSymbolVersion(exp);
      symbol.versions.push(symbolVersion);
    } else {
      symbolVersion.experiments.push(exp);
    }
  }

  return {
    // When creating a new UI state from an experiment list, all symbols
    // should be selected by default.
    selectedSymbols: Object.keys(symbols),
    contextMenu: { __kind__: ContextMenuKind.Experiment },
    symbols,
  };
}

function newSymbol(name: string, versions: string[]): Symbol {
  return {
    name,
    selectedVersions: versions,
    versions: [],
  };
}

function newSymbolVersion(exp: Experiment): SymbolVersion {
  return {
    digest: exp.fn_hash,
    selectedParams: exp.args.map((a) => a.name),

    // When creating a new SymbolVersion, we have no user-defined column
    // layouts, so this is empty, and defaults will be used when rendering.
    columns: {},
    params: exp.args.map((arg) => argToParam(arg)),
    experiments: [exp],
  };
}

function argToParam(arg: Arg): Param {
  return {
    name: arg.name,
    annotation: arg.annotation,
    kind: arg.kind,
    docs: arg.docs,
  };
}
