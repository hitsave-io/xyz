import * as React from "react";
import * as ReactDOM from "react-dom";

export const Greet = () => <h1>Hello, world!</h1>;

const elt = document.getElementById("react-root");
ReactDOM.render(<Greet />, elt);
// hello workd asdf
