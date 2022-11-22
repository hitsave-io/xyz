import * as React from "react";
import { ClientOnly } from "./clientonly";

export interface Arg {
  name: string;
  value: VisualObject;
  is_default?: boolean;
  annotation?: VisualObject;
  kind?: number;
  docs?: string;
}

type Kind = "object" | "html" | "image" | "plotly" | "blob" | "opaque";

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

interface Basic {
  __kind__?: "object";
  __class__?: string;
  /** If __truncated__ is a number > 0, it means that some elements have been omitted from the visualisation */
  __truncated__?: number;
  // other things go here.
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
  | Basic
  | Plotly
  | Blob
  | Image
  | number
  | string
  | boolean
  | null
  | VisualObject[]
  | { [k: string]: VisualObject };

function isList(v: VisualObject): v is VisualObject[] {
  return v instanceof Array;
}

function isDict(v: VisualObject): v is { [k: string]: VisualObject } {
  if (typeof v !== "object") {
    return false;
  }
  if (!v) {
    return false;
  }
  if (Object.hasOwnProperty.call(v, "__kind__")) {
    return false;
  }
  return true;
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
export function Show(props: { o: VisualObject; depth?: number }) {
  const depth = props.depth ?? 0;
  const o = props.o;
  if (o === null) {
    return <span>None</span>;
  } else if (typeof o === "boolean") {
    if (o) {
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
  } else if (typeof o === "number") {
    return <span className="font-semibold text-orange-700">{o}</span>;
  } else if (typeof o === "string") {
    // [todo] if too long?
    return <span>{o}</span>;
  } else if (isList(o)) {
    // [todo] too long? collapsible?
    let items: any[] = o;
    let isTruncated = false;
    if (items.length > 0) {
      const last = items[items.length - 1];
      if (isDict(last) && last.__truncated__) {
        items = items.slice(0, o.length - 1);
        isTruncated = true;
      }
    }
    const cs = items.map((x, i) => <Show key={i} o={x} depth={depth + 1} />);

    if (isTruncated) {
      items.push(<span>...</span>);
    }
    return <span>[{interlace(items, <>, </>)}]</span>;
  } else if (isDict(o) || o.__kind__ === "object") {
    // [todo] should pretty print on multiple lines if there is space.
    const isTruncated = !!o.__truncated__;
    const keys = Object.getOwnPropertyNames(o).filter((k) =>
      k.startsWith("__")
    );
    return (
      <span>
        {"{"}
        {keys.map((k) => (
          <span key={k}>
            {k} : <Show o={(o as any)[k]} depth={depth + 1} />
          </span>
        ))}
        {isTruncated && <span>...</span>}
        {"}"}
      </span>
    );
  } else if (o.__kind__ === "opaque") {
    if (!o.repr) {
      return (
        <span className="font-semibold text-blue-700">⟨{o.__class__}⟩</span>
      );
    } else {
      return <span className="font-semibold text-sky-700">{o.repr}</span>;
    }
  } else if (o.__kind__ === "plotly") {
    const { data, layout } = JSON.parse(o.value);
    // ref: https://github.com/remix-run/remix/discussions/2936
    return (
      <ClientOnly>
        <React.Suspense fallback="loading">
          <Plot data={data} layout={layout} />
        </React.Suspense>
      </ClientOnly>
    );
  } else if (o.__kind__ === "html") {
    const children = o.children.map((c, i) => (
      <Show o={c} depth={depth + 1} key={i} />
    ));
    return React.createElement(o.tag, o.attrs, ...children);
  } else if (o.__kind__ === "blob") {
    throw "blob visualisations not implemented";
  } else if (o.__kind__ === "image") {
    const api_url = "http://127.0.0.1:8080"
    const src = `${api_url}/blob/${o.digest}`;
    /* Need to use object instead of image so that we can dynamically set the mime type.
       The blob server doesn't know about mime types.
       As a side effect, this also means we can show other things like pdfs. */
    return <object type={o.mime_type} data={src} />;
  } else {
    throw "not implemented";
  }
}

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
