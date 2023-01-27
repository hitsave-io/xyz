import * as React from "react";
import { createRoot } from "react-dom/client";
import { JsonRpc } from "./rpc";
declare const acquireVsCodeApi: any;
// const vscode = acquireVsCodeApi();

export const Greet = () => <h1>Hello from React!!!</h1>;

const elt = document.getElementById("react_root");
const root = createRoot(elt!);

interface Fiber {
  id: number;
  kind: "Fiber";
  name: string;
  children: Spec[];
}
interface Elt {
  kind: "Element";
  tag: string;
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
    return React.createElement(s.tag, s.attrs, s.children.map(Render));
  }
}

function RenderRoot() {
  const [x, setX] = React.useState<any>(undefined);
  React.useEffect(() => {
    rpc.request("render", {}).then((x) => {
      console.log("render returned");
      setX(x);
    });
  }, []);
  if (x) {
    const cs = x.map((x) => React.createElement(Render, x));
    return <>{cs}</>;
  } else {
    return <h1>Loading</h1>;
  }
}

const sock = new WebSocket("ws://localhost:7787");
const rpc = new JsonRpc(sock);

rpc.handleReady = () => root.render(<RenderRoot />);
