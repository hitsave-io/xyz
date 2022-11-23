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
  { tag: t.punctuation, class: "punctuation" },
  { tag: t.link, class: "link" },
  { tag: t.heading, class: "heading" },
  { tag: t.emphasis, class: "emphasis" },
  { tag: t.strong, class: "strong" },
  { tag: t.keyword, class: "keyword" },
  { tag: t.atom, class: "atom" },
  { tag: t.bool, class: "bool" },
  { tag: t.url, class: "bool" },
  { tag: t.labelName, class: "labelName" },
  { tag: t.inserted, class: "inserted" },
  { tag: t.deleted, class: "deleted" },
  { tag: t.literal, class: "deleted" },
  { tag: t.string, class: "string" },
  { tag: t.number, class: "number" },
  { tag: [t.regexp, t.escape, t.special(t.string)], class: "string2" },
  { tag: t.variableName, class: "variableName" },
  { tag: t.local(t.variableName), class: "localVariableName" },
  {
    tag: t.definition(t.variableName),
    class: "definitionVariableName",
  },
  { tag: t.special(t.variableName), class: "variableName2" },
  {
    tag: t.definition(t.propertyName),
    class: "definitionPropertyName",
  },
  { tag: t.typeName, class: "typeName" },
  { tag: t.namespace, class: "namespace" },
  { tag: t.className, class: "className" },
  { tag: t.macroName, class: "macroName" },
  { tag: t.propertyName, class: "propertyName" },
  { tag: t.operator, class: "operator" },
  { tag: t.comment, class: "comment" },
  { tag: t.meta, class: "decorator" },
  { tag: t.invalid, class: "invalid" },
  { tag: t.function(t.variableName), class: "functionCall" },
  {
    tag: t.function(t.definition(t.variableName)),
    class: "functionDefinition",
  },
  { tag: t.definition(t.meta), class: "decorator" },
]);

const codeString = `lr = 0.01
batch_size = 100

def test():
    model = train(100)
    accuracy = evaluate(model, test_data)
    return accuracy

def train(epochs):
    model = RCNN(lr, batch_size)
    model.train(epochs, train_data)
    return model
    
model = train()
print(test(model))`;

const codeFactory: (init: string, setState: any) => Code = (init, setState) => {
  return new Code(init, setState)
    .setCursor(0)
    .wait(2000)
    .typeLine(
      `

`,
      250
    )
    .setCursor(0)
    .typeLine(`from hitsave import experiment, memo`, 100)
    .setCursor(65)
    .typeLine(
      `
`,
      125
    )
    .wait(750)
    .setCursor(66)
    .typeLine(`@experiment`, 100)
    .wait(1500)
    .setCursor(175)
    .typeLine(
      `
`,
      125
    )
    .wait(750)
    .setCursor(176)
    .typeLine(`@memo`, 100)
    .wait(1500)
    .setCursor(37)
    .typeLine(
      `
`,
      100
    )
    .wait(750)
    .setCursor(38)
    .typeLine(`# Run some different experiments!!`, 100);
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
    <div className={"screen"}>
      <WindowButtons />
      <Title title="" />
      <CodeBlock code={code} cursor={cursor} />
    </div>
  );
};

const WindowButtons: React.FC = () => {
  return (
    <div className={"buttons"}>
      <div className={"circ"}></div>
      <div className={"circ"}></div>
      <div className={"circ"}></div>
    </div>
  );
};

const Title: React.FC<{ title: String }> = ({ title }) => {
  return <div className={"title"}>{title}</div>;
};

const CodeBlock: React.FC<{ code: string; cursor: number }> = ({
  code,
  cursor,
}) => {
  let tree = parser.parse(code);
  let el = fromLezer(code, tree, cursor);
  let hast = toH(createElement, el);

  return (
    <div className={"codeBlock"}>
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
        this.pushCursor("cursor");
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
      properties: { className: "codeLine" },
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
    properties: { className: "lineNumber" },
  };
}

/// Returns whether the cursor lies between from and to.
function cursorBetween(cursor: number, from: number, to: number): boolean {
  return from <= cursor && cursor <= to;
}
