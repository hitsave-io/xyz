import * as React from "react";
import { createRoot } from "react-dom/client";
import { JsonRpc } from "./rpc";
declare const acquireVsCodeApi: any;
// const vscode = acquireVsCodeApi();

export const Greet = () => <h1>Hello from React!!!</h1>;

const elt = document.getElementById("react_root");
const root = createRoot(elt!);

interface EventArgs {
  element_id: number;
  name: string;
  params: any;
}

interface Fiber {
  id: number;
  kind: "Fiber";
  name: string;
  children: Spec[];
}
interface Elt {
  kind: "Element";
  tag: string;
  id: number;
  attrs: any;
  children: Spec[];
}
interface Text {
  kind: "Text";
  value: string;
}
type Spec = Text | Elt | Fiber;
function RenderFiber(props: Fiber): any {
  return props.children.map(Render);
}

function Render(s: Spec): any {
  if (s.kind === "Text") {
    return s.value;
  } else if (s.kind === "Fiber") {
    return React.createElement(RenderFiber, { ...s, key: s.id });
  } else {
    const attrs: any = {};
    attrs.key = s.id;
    for (const key of Object.keys(s.attrs)) {
      const v = s.attrs[key];
      if (typeof v == "object" && "__handler__" in v) {
        attrs[key] = () =>
          rpc.notify("event", { element_id: s.id, name: key, params: {} });
      } else {
        attrs[key] = v;
      }
    }

    return React.createElement(s.tag, attrs, s.children.map(Render));
  }
}

function RenderRoot({ cs }: { cs: Spec[] }) {
  if (cs) {
    const xs = cs.map((x: Spec, i) =>
      React.createElement(Render, { key: i, ...x })
    );
    return <>{xs}</>;
  } else {
    return <h1>Loading</h1>;
  }
}

const sock = new WebSocket("ws://localhost:7787");
const rpc = new JsonRpc(sock);

async function render_root() {
  console.log("requesting rerender");
  let children = await rpc.request("render", {});
  console.log("got rerender response");
  root.render(<RenderRoot cs={children} />);
}

rpc.register("patch", async (patches: any) => {
  console.log(`patch:`, patches);
  await render_root();
  return "success";
});

rpc.handleReady = async () => {
  await render_root();
};
