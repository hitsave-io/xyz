import * as React from "react";
import { createRoot } from "react-dom/client";
import { JsonRpc } from "./rpc";
declare const acquireVsCodeApi: any;
// const vscode = acquireVsCodeApi();

export const Greet = () => <h1>Hello from React!!!</h1>;

const elt = document.getElementById("react_root");
const root = createRoot(elt!);

const sock = new WebSocket("ws://localhost:7787");
const rpc = new JsonRpc(sock);

function Derper(props: any) {
  const [derps, dispatch] = React.useReducer(
    (state: any, action: any) => [...state, action],
    []
  );
  React.useEffect(() => {
    return rpc.sub("derp", dispatch);
  });
  return (
    <>
      <Greet />
      <ol>
        {derps.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ol>
    </>
  );
}

root.render(<Derper />);
