import * as React from "react";
import { AppContext } from "~/root";
import { hasOwnProperty } from "~/utils/hasOwnProperty";
import { ClientOnly } from "./clientonly";

interface Html {
  __kind__: "html";
  tag: string;
  attrs: { [k: string]: any };
  children: VisualObject[];
}

interface Opaque {
  __kind__: "opaque";
  __class__: string;
  repr?: string;
}

interface Obj {
  __kind__?: "object";
  __class__?: string;
  /** If `truncated` is a number > 0, it means that some elements have been omitted from the visualisation */
  truncated?: number;
  values: { [key: string]: VisualObject };
}

interface List {
  __class__: "list";
  truncated?: number | false;
  values: VisualObject[];
}

interface Dict {
  __class__: "dict";
  truncated: number | false;
  values: { [key: string]: VisualObject };
}

interface Blob {
  __kind__: "blob";
  // [todo]
}

interface Plotly {
  __kind__: "plotly";
  /** Plotly JSON encoding. */
  value: string;
}

interface Image {
  __kind__: "image";
  digest: string;
  content_length: number;
  mime_type: string;
}

export type VisualObject =
  | Html
  | Opaque
  | Obj
  | Plotly
  | Blob
  | Image
  | number
  | string
  | List
  | Dict
  | boolean
  | null
  | VisualObject[]
  | { [k: string]: VisualObject };

function isKind<T extends VisualObject>(v: VisualObject, kind: string): v is T {
  if (v !== null && hasOwnProperty(v, "__kind__")) {
    return v.__kind__ === kind;
  } else {
    return false;
  }
}

function isObj(v: VisualObject): v is Obj {
  return isKind<Obj>(v, "object");
}

function isHtml(v: VisualObject): v is Html {
  return isKind<Html>(v, "html");
}

function isOpaque(v: VisualObject): v is Opaque {
  return isKind<Opaque>(v, "opaque");
}

function isPlotly(v: VisualObject): v is Plotly {
  return isKind<Plotly>(v, "plotly");
}

function isBlob(v: VisualObject): v is Blob {
  return isKind<Blob>(v, "blob");
}

function isImage(v: VisualObject): v is Image {
  return isKind<Image>(v, "image");
}

function isClass<T extends VisualObject>(v: VisualObject, cls: string): v is T {
  return !!v && hasOwnProperty(v, "__class__") && v.__class__ === cls;
}

function isList(v: VisualObject): v is List | [] {
  return Array.isArray(v) || isClass<List>(v, "list");
}

function isDict(v: VisualObject): v is Dict {
  return isClass<Dict>(v, "dict");
}

/* The Show function renders these visual objects.

The tricky bit is figuring out how much information to show to the user.

- [ ] There should be a 'fully expanded' modal that lets you see the whole unabridged object.
- [ ] something like responsive design should be used, where each object has various representations depending on the size available.
- [ ] should be a mode : 'inline' | 'block' dictating whether there are multiple lines.

https://github.com/remix-run/remix/discussions/2936

*/
// @ts-ignore
const Plot = React.lazy(() => import("./react-plotly"));

export interface ShowProps {
  o: VisualObject;
  depth?: number;
  detailed?: boolean;
}

export const Show: React.FC<ShowProps> = ({
  o,
  depth = 1,
  detailed = false,
}) => {
  if (o === null) {
    return <span>None</span>;
  } else if (typeof o === "boolean") {
    return <ShowBoolean val={o} />;
  } else if (typeof o === "number") {
    return <ShowNumber val={o} />;
  } else if (typeof o === "string") {
    return <ShowString val={o} />;
  } else if (isList(o)) {
    return <ShowList val={o} depth={depth + 1} detailedChildren={detailed} />;
  } else if (isDict(o) || isObj(o)) {
    return <ShowDict val={o} depth={depth + 1} multiline={detailed} />;
  } else if (isOpaque(o)) {
    return <ShowOpaque val={o} />;
  } else if (isPlotly(o)) {
    return <ShowPlotly val={o} />;
  } else if (isHtml(o)) {
    return <ShowHtml val={o} depth={depth + 1} />;
  } else if (isBlob(o)) {
    return <ShowUnknown message="Blob visualisations not implemented" />;
  } else if (isImage(o)) {
    return <BlobObject data={o} collapsed={!detailed} />;
  } else {
    return (
      <ShowUnknown message="Unknown value type. Don't know how to visualize." />
    );
  }
};

interface ShowStringProps {
  quoted?: boolean;
  val: string;
}

const ShowString: React.FC<ShowStringProps> = ({ val, quoted = false }) => {
  // [todo] if too long?
  return (
    <>
      {quoted && <span className="font-semibold text-gray-500">"</span>}
      <span className="font-medium text-green-700">{val}</span>
      {quoted && <span className="font-semibold text-gray-500">"</span>}
    </>
  );
};

interface ShowNumberProps {
  val: number;
}

const ShowNumber: React.FC<ShowNumberProps> = ({ val }) => {
  return <span className="font-semibold text-orange-500">{val}</span>;
};

interface ShowBooleanProps {
  val: boolean;
}

const ShowBoolean: React.FC<ShowBooleanProps> = ({ val }) => {
  if (val === true) {
    return (
      <span className="mr-1 whitespace-nowrap rounded-full bg-green-700 px-2 py-1 leading-6 font-semibold text-white shadow-md select-none">
        True
      </span>
    );
  } else {
    return (
      <span className="mr-1 whitespace-nowrap rounded-full bg-red-700 px-2 py-1 leading-6 font-semibold text-white shadow-md select-none">
        False
      </span>
    );
  }
};

interface ShowOpaqueProps {
  val: Opaque;
}

const ShowOpaque: React.FC<ShowOpaqueProps> = ({ val }) => {
  if (!val.repr) {
    return (
      <span className="font-semibold text-blue-700">⟨{val.__class__}⟩</span>
    );
  } else {
    return <span className="font-semibold text-sky-700">{val.repr}</span>;
  }
};

interface ShowHtmlProps {
  val: Html;
  depth?: number;
}

const ShowHtml: React.FC<ShowHtmlProps> = ({ val, depth }) => {
  const children: React.ReactNode[] = val.children.map((c, i) => {
    return <Show o={c} depth={depth} key={i} />;
  });
  return React.createElement(val.tag, val.attrs, ...children);
};

interface ShowListProps {
  val: List | [];
  depth?: number;
  detailedChildren?: boolean;
}

const ShowList: React.FC<ShowListProps> = ({
  val,
  depth,
  detailedChildren = false,
}) => {
  // [todo] too long? collapsible?
  let items = Array.isArray(val) ? val : val.values;
  let isTruncated = false;
  if (items.length > 0) {
    const last = items[items.length - 1];
    if (isDict(last) && last.truncated) {
      items = items.slice(0, items.length - 1);
      isTruncated = true;
    }
  }
  const cs = items.map((x, i) => (
    <Show key={i} o={x} depth={depth} detailed={detailedChildren} />
  ));

  // if (isTruncated) {
  //   items.push(<span>...</span>);
  // }
  return <span>[{...interlace(cs, <>, </>)}]</span>;
};

interface ShowDictProps {
  val: Obj | Dict;
  depth?: number;
  multiline?: boolean;
}

const ShowDict: React.FC<ShowDictProps> = ({
  val,
  depth,
  multiline = false,
}) => {
  const isTruncated = !!val.truncated;
  const entries = Object.entries(val.values);

  if (multiline) {
    return (
      <div className="flex flex-col">
        <div>{"{"}</div>
        {entries.map(([k, v]) => {
          // If the value for this entry is a string, we display it as quoted.
          const val =
            typeof v === "string" ? (
              <ShowString val={v} quoted />
            ) : (
              <Show o={v} depth={depth} />
            );

          return (
            <div key={k}>
              &nbsp;&nbsp;
              <ShowString val={k} quoted />: {val}
              {", "}
            </div>
          );
        })}
        {isTruncated && <span>...</span>}
        <div>{"}"}</div>
      </div>
    );
  } else {
    return (
      <>
        {"{"}
        {entries.map(([k, v], idx) => {
          // If the value for this entry is a string, we display it as quoted.
          const val =
            typeof v === "string" ? (
              <ShowString val={v} quoted />
            ) : (
              <Show o={v} depth={depth} />
            );

          return (
            <React.Fragment key={k}>
              <ShowString val={k} quoted />: {val}
              {idx + 1 !== entries.length ? ", " : ""}
            </React.Fragment>
          );
        })}
        {isTruncated && <span>...</span>}
        {"}"}
      </>
    );
  }
};

interface ShowPlotlyProps {
  val: Plotly;
}

const ShowPlotly: React.FC<ShowPlotlyProps> = ({ val }) => {
  const { data, layout } = JSON.parse(val.value);
  // ref: https://github.com/remix-run/remix/discussions/2936
  return (
    <ClientOnly>
      <React.Suspense fallback="loading">
        <Plot data={data} layout={layout} />
      </React.Suspense>
    </ClientOnly>
  );
};

interface ShowUnknownProps {
  message: string;
}

const ShowUnknown: React.FC<ShowUnknownProps> = ({ message }) => {
  // todo: display message in a tooltip or something?
  console.error(message);
  return <span>{"<value>"}</span>;
};

interface BlobObjectProps {
  data: Image;
  collapsed?: boolean;
}

const BlobObject: React.FC<BlobObjectProps> = ({ data, collapsed = true }) => {
  const appContext = React.useContext(AppContext);
  const api_url = appContext.api_url;
  const src = `${api_url}/blob/${data.digest}`;
  /* Need to use object instead of image so that we can dynamically set the mime type.
     The blob server doesn't know about mime types.
     As a side effect, this also means we can show other things like pdfs. */
  if (collapsed) {
    return <span>{"<Image>"}</span>;
  } else {
    return <object type={data.mime_type} data={src} className="w-full" />;
  }
};

function interlace<T>(xs: T[], sep: T): T[] {
  if (xs.length == 0) {
    return xs;
  }
  const out = [xs[0]];
  for (let i = 1; i < xs.length; i++) {
    out.push(sep, xs[i]);
  }
  return out;
}
