export interface ParsedSseEvent {
  id?: string;
  event?: string;
  data: string;
}

export interface ParsedSseChunk {
  events: ParsedSseEvent[];
  remainder: string;
}

export function parseSseChunk(buffer: string): ParsedSseChunk {
  const events: ParsedSseEvent[] = [];
  let event: ParsedSseEvent = { data: "" };
  let hasData = false;
  let lastNewline = -1;
  let lineStart = 0;
  let eventStart: number | null = null;

  for (let index = 0; index < buffer.length; index += 1) {
    if (buffer[index] !== "\n") continue;
    lastNewline = index;
    const currentLineStart = lineStart;
    let line = buffer.slice(lineStart, index);
    if (line.endsWith("\r")) line = line.slice(0, -1);
    lineStart = index + 1;

    if (line === "") {
      if (hasData) events.push(event);
      event = { data: "" };
      hasData = false;
      eventStart = null;
      continue;
    }
    if (line.startsWith(":")) continue;

    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    const value =
      separator < 0
        ? ""
        : line.slice(separator + 1).replace(/^ /, "");
    if (
      field === "data" ||
      field === "event" ||
      (field === "id" && !value.includes("\0"))
    ) {
      eventStart ??= currentLineStart;
    }
    if (field === "data") {
      event.data = hasData ? `${event.data}\n${value}` : value;
      hasData = true;
    } else if (field === "id" && !value.includes("\0")) {
      event.id = value;
    } else if (field === "event") {
      event.event = value;
    }
  }

  const remainder = buffer.slice(eventStart ?? lastNewline + 1);
  return { events, remainder };
}
