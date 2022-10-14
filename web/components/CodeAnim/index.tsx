import * as React from "react";
import { Code } from "./code";
import { Tree } from "@lezer/common";
import { parser as pythonParser } from "@lezer/python";
import {
  highlightTree,
  tagHighlighter,
  tags as t,
  styleTags,
} from "@lezer/highlight";
import { toH } from "hast-to-hyperscript";
import type { Root, Element, Text } from "hast";

import styles from "./CodeAnim.module.scss";

const { createElement, useEffect, useState, useRef } = React;

let parser = pythonParser.configure({
  props: [
    styleTags({
      'async "*" "**" FormatConversion FormatSpec': t.modifier,
      "for while if elif else try except finally return raise break continue with pass assert await yield":
        t.controlKeyword,
      "in not and or is del": t.operatorKeyword,
      "from def class global nonlocal lambda": t.definitionKeyword,
      import: t.moduleKeyword,
      "with as print": t.keyword,
      Boolean: t.bool,
      None: t.null,
      VariableName: t.variableName,
      "CallExpression/VariableName": t.function(t.variableName),
      "FunctionDefinition/VariableName": t.function(
        t.definition(t.variableName)
      ),
      "ClassDefinition/VariableName": t.definition(t.className),
      PropertyName: t.propertyName,
      "CallExpression/MemberExpression/PropertyName": t.function(
        t.propertyName
      ),
      Comment: t.lineComment,
      Number: t.number,
      String: t.string,
      FormatString: t.special(t.string),
      UpdateOp: t.updateOperator,
      ArithOp: t.arithmeticOperator,
      BitOp: t.bitwiseOperator,
      CompareOp: t.compareOperator,
      AssignOp: t.definitionOperator,
      Ellipsis: t.punctuation,
      At: t.meta,
      "Decorator/VariableName": t.definition(t.meta),
      "( )": t.paren,
      "[ ]": t.squareBracket,
      "{ }": t.brace,
      ".": t.derefOperator,
      ", ;": t.separator,
      ":": t.punctuation,
    }),
  ],
});

const highlighter = tagHighlighter([
  { tag: t.punctuation, class: styles.punctuation },
  { tag: t.link, class: styles.link },
  { tag: t.heading, class: styles.heading },
  { tag: t.emphasis, class: styles.emphasis },
  { tag: t.strong, class: styles.strong },
  { tag: t.keyword, class: styles.keyword },
  { tag: t.atom, class: styles.atom },
  { tag: t.bool, class: styles.bool },
  { tag: t.url, class: styles.bool },
  { tag: t.labelName, class: styles.labelName },
  { tag: t.inserted, class: styles.inserted },
  { tag: t.deleted, class: styles.deleted },
  { tag: t.literal, class: styles.deleted },
  { tag: t.string, class: styles.string },
  { tag: t.number, class: styles.number },
  { tag: [t.regexp, t.escape, t.special(t.string)], class: styles.string2 },
  { tag: t.variableName, class: styles.variableName },
  { tag: t.local(t.variableName), class: styles.localVariableName },
  {
    tag: t.definition(t.variableName),
    class: styles.definitionVariableName,
  },
  { tag: t.special(t.variableName), class: styles.variableName2 },
  {
    tag: t.definition(t.propertyName),
    class: styles.definitionPropertyName,
  },
  { tag: t.typeName, class: styles.typeName },
  { tag: t.namespace, class: styles.namespace },
  { tag: t.className, class: styles.className },
  { tag: t.macroName, class: styles.macroName },
  { tag: t.propertyName, class: styles.propertyName },
  { tag: t.operator, class: styles.operator },
  { tag: t.comment, class: styles.comment },
  { tag: t.meta, class: styles.decorator },
  { tag: t.invalid, class: styles.invalid },
  { tag: t.function(t.variableName), class: styles.functionCall },
  {
    tag: t.function(t.definition(t.variableName)),
    class: styles.functionDefinition,
  },
  { tag: t.definition(t.meta), class: styles.decorator },
]);

const codeString = `def dependency(y):
  # try changing the method body!
  return y + y

def long_running_function(x):
  print f"Running {x}!"
  return x + 2 + dependency(x)

long_running_function(3)
long_running_function(4)`;

const codeFactory: (init: string, setState: any) => Code = (init, setState) => {
  return new Code(init, setState)
    .setCursor(0)
    .wait(2000)
    .typeLine(
      `

`,
      150
    )
    .setCursor(0)
    .typeLine(`from hitsave import save`, 125)
    .setCursor(95)
    .typeLine(
      `
`,
      125
    )
    .wait(1500)
    .setCursor(95)
    .typeLine(`@save`, 125);
};

export const CodeAnim: React.FC = () => {
  const [code, setCode] = useState<string>("");
  const ref = useRef(codeFactory(codeString, setCode));

  useEffect(() => {
    setCode(ref.current.val);
    ref.current.play();
  }, [ref.current]);

  return <Screen code={code} cursor={ref.current.getCursor()} />;
};

const Screen: React.FC<{ code: string; cursor: number }> = ({
  code,
  cursor,
}) => {
  return (
    <div className={styles.screen}>
      <WindowButtons />
      <Title title="" />
      <CodeBlock code={code} cursor={cursor} />
    </div>
  );
};

const WindowButtons: React.FC = () => {
  return (
    <div className={styles.buttons}>
      <div className={styles.circ}></div>
      <div className={styles.circ}></div>
      <div className={styles.circ}></div>
    </div>
  );
};

const Title: React.FC<{ title: String }> = ({ title }) => {
  return <div className={styles.title}>{title}</div>;
};

const CodeBlock: React.FC<{ code: string; cursor: number }> = ({
  code,
  cursor,
}) => {
  let tree = parser.parse(code);
  let el = fromLezer(code, tree, cursor);
  let hast = toH(createElement, el);

  return (
    <div className={styles.codeBlock}>
      <pre>
        <code>{hast}</code>
      </pre>
    </div>
  );
};

class Renderer {
  children: (Element | Text)[];
  line: (Element | Text)[];
  lineNumber: number;
  index: number;

  constructor() {
    this.children = [];
    this.line = [];
    this.lineNumber = 1;
    this.index = 0;
  }

  render(source: string, tree: Tree, cursor: number): Root {
    highlightTree(tree, highlighter, (from, to, classes) => {
      if (from > this.index) {
        this.pushText(source.slice(this.index, from));
      }

      if (cursorBetween(cursor, from, to)) {
        this.pushSpan(source.slice(from, cursor), classes);
        this.pushCursor(styles.cursor);
        this.pushSpan(source.slice(cursor, to), classes);
      } else {
        this.pushSpan(source.slice(from, to), classes);
      }

      this.index = to;
    });

    if (this.index < source.length) {
      this.pushText(source.slice(this.index));
    }

    this.pushLine();

    return {
      type: "root",
      children: this.children,
    };
  }

  pushCursor(classes: string) {
    this.line.push({
      type: "element",
      tagName: "span",
      properties: { className: classes },
      children: [],
    });
  }

  pushSpan(text: string, classes: string) {
    this.line.push({
      type: "element",
      tagName: "span",
      properties: { className: classes },
      children: [
        {
          type: "text",
          value: text,
        },
      ],
    });
  }

  pushText(text: string) {
    text.split("\n").forEach((text, idx, segments) => {
      this.line.push({
        type: "element",
        tagName: "span",
        children: [
          {
            type: "text",
            value: text,
          },
        ],
      });
      if (idx + 1 < segments.length) {
        this.pushLine();
      }
    });
  }

  pushLine() {
    const gutter = gutterSpan(this.lineNumber);
    this.lineNumber += 1;

    this.children.push({
      type: "element",
      tagName: "div",
      properties: { className: styles.codeLine },
      children: [gutter, ...this.line],
    });

    this.line = [];
  }
}

function fromLezer(source: string, tree: Tree, cursor: number) {
  let renderer = new Renderer();
  return renderer.render(source, tree, cursor);
}

function gutterSpan(lineNumber: number): Element {
  return {
    type: "element",
    tagName: "span",
    children: [{ type: "text", value: lineNumber.toString() }],
    properties: { className: styles.lineNumber },
  };
}

/// Returns whether the cursor lies between from and to.
function cursorBetween(cursor: number, from: number, to: number): boolean {
  return from <= cursor && cursor <= to;
}
