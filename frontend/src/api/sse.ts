/**
 * Manual SSE parsing over `fetch`'s streaming body, used for both the GET
 * /stream and POST /resume endpoints. The native `EventSource` API can't send
 * the `X-API-Key` header or issue POST requests, so both call this instead of
 * mixing two different transports.
 */

export interface SSEEvent {
  event: string;
  data: string;
}

export async function streamSSE(
  url: string,
  init: RequestInit,
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  const resp = await fetch(url, init);
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => resp.statusText);
    throw new Error(`stream error ${resp.status}: ${text}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // sse-starlette (and the SSE spec generally) separate events with a blank
  // line, but the line ending can be "\n\n" or "\r\n\r\n" depending on the
  // server — match either rather than assuming one.
  const EVENT_BOUNDARY = /\r\n\r\n|\n\n/;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let match = buffer.match(EVENT_BOUNDARY);
    while (match && match.index !== undefined) {
      const rawEvent = buffer.slice(0, match.index);
      buffer = buffer.slice(match.index + match[0].length);
      const parsed = parseEvent(rawEvent);
      if (parsed) onEvent(parsed);
      match = buffer.match(EVENT_BOUNDARY);
    }
  }
}

function parseEvent(raw: string): SSEEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}
