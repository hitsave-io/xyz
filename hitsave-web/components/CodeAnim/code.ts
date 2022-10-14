interface AnimEventMoveCursor {
  ty: "move-cursor";
  to: [number, number];
}

interface AnimEventWait {
  ty: "wait";
  delay: number;
}

interface AnimEventTypeLetter {
  ty: "type-letter";
  letter: string;
}

interface AnimEventSetCursor {
  ty: "set-cursor";
  pos: number;
}

type AnimEvent =
  | AnimEventMoveCursor
  | AnimEventWait
  | AnimEventTypeLetter
  | AnimEventSetCursor;

export class Code {
  val: string;
  cursor: number;
  cb: (code: string) => any;
  animEvents: AnimEvent[];

  constructor(code: string, cb: (code: string) => any) {
    this.val = code;
    this.cursor = 0;
    this.cb = cb;
    this.animEvents = [];
  }

  getCursor(): number {
    return this.cursor;
  }

  setCursor(pos: number): Code {
    this.animEvents.push({
      ty: "set-cursor",
      pos,
    });

    return this;
  }

  typeLetter(letter: string): Code {
    this.animEvents.push({
      ty: "type-letter",
      letter,
    });

    return this;
  }

  typeLine(line: string, rate: number): Code {
    // `rate` is the number of milliseconds between each character.
    for (const letter of line) {
      this.animEvents.push({
        ty: "type-letter",
        letter,
      });

      this.wait(rate);
    }

    return this;
  }

  wait(delay: number): Code {
    this.animEvents.push({
      ty: "wait",
      delay,
    });

    return this;
  }

  getNextEvent(): AnimEvent | undefined {
    return this.animEvents.shift();
  }

  processEvent() {
    const nextEvent = this.getNextEvent();

    if (!nextEvent) return;

    switch (nextEvent.ty) {
      case "move-cursor":
        this.processEvent();
        break;

      case "wait":
        setTimeout(() => {
          this.processEvent();
        }, nextEvent.delay);
        break;

      case "type-letter":
        const output = [
          this.val.slice(0, this.cursor),
          nextEvent.letter,
          this.val.slice(this.cursor),
        ].join("");
        this.val = output;
        this.cursor += 1;
        this.cb(this.val);
        this.processEvent();
        break;

      case "set-cursor":
        this.cursor = nextEvent.pos;
        this.cb(this.val);
        this.processEvent();
        break;
    }
  }

  play() {
    this.processEvent();
  }
}
