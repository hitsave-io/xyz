import * as React from "react";
import { createRoot } from "react-dom/client";
declare const acquireVsCodeApi: any;
// const vscode = acquireVsCodeApi();

export const Greet = () => <h1>Hello from React!!!</h1>;

const elt = document.getElementById("react_root");
const root = createRoot(elt!);
root.render(<Greet />);
