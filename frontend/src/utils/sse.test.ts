import { describe, expect, it } from "vitest";
import { parseSseChunk } from "./sse";

describe("parseSseChunk", () => {
  it("keeps an incomplete event as a remainder", () => {
    expect(
      parseSseChunk('id: 7\nevent: experiment_event\ndata: {"seq":'),
    ).toEqual({
      events: [],
      remainder: 'id: 7\nevent: experiment_event\ndata: {"seq":',
    });
  });

  it("completes an event by appending the next chunk to the first remainder", () => {
    const first = parseSseChunk(
      'id: 7\nevent: experiment_event\ndata: {"seq":',
    );
    const second = parseSseChunk(`${first.remainder}42}\n\n`);

    expect(second).toEqual({
      events: [
        {
          id: "7",
          event: "experiment_event",
          data: '{"seq":42}',
        },
      ],
      remainder: "",
    });
  });

  it("parses CRLF line endings like LF line endings", () => {
    expect(
      parseSseChunk(
        "id: 12\r\nevent: experiment_event\r\ndata: first\r\ndata: second\r\n\r\n",
      ),
    ).toEqual(
      parseSseChunk(
        "id: 12\nevent: experiment_event\ndata: first\ndata: second\n\n",
      ),
    );
  });

  it("parses multiline data, id and event fields", () => {
    expect(
      parseSseChunk("id: 12\nevent: experiment_event\ndata: first\ndata: second\n\n"),
    ).toEqual({
      events: [
        {
          id: "12",
          event: "experiment_event",
          data: "first\nsecond",
        },
      ],
      remainder: "",
    });
  });

  it("ignores comment lines and leaves the next partial line buffered", () => {
    expect(
      parseSseChunk(": keepalive\nid: 3\ndata: value\n\nid: 4\ndata:"),
    ).toEqual({
      events: [{ id: "3", data: "value" }],
      remainder: "id: 4\ndata:",
    });
  });
});
