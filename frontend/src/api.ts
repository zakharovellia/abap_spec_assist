async function check(res: Response): Promise<Response> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      /* тело не JSON — оставляем statusText */
    }
    throw new Error(detail);
  }
  return res;
}

export async function createSession(): Promise<string> {
  const res = await check(await fetch("/api/sessions", { method: "POST" }));
  return (await res.json()).session_id as string;
}

export interface StreamHandlers {
  onToken: (text: string) => void;
  onStatus: (value: string, tool?: string) => void;
  onSpec: (markdown: string) => void;
  onDone: (reply: string, specMarkdown: string) => void;
}

export async function streamMessage(
  sessionId: string,
  content: string,
  handlers: StreamHandlers,
): Promise<void> {
  const res = await check(
    await fetch(`/api/sessions/${sessionId}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }),
  );
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const event = JSON.parse(line.slice(6));
        switch (event.type) {
          case "token":
            handlers.onToken(event.text);
            break;
          case "status":
            handlers.onStatus(event.value, event.tool);
            break;
          case "spec":
            handlers.onSpec(event.markdown);
            break;
          case "done":
            handlers.onDone(event.reply, event.spec_markdown);
            break;
          case "error":
            throw new Error(event.detail);
        }
      }
    }
  }
}

export async function fetchExamplesStats(): Promise<number> {
  const res = await check(await fetch("/api/examples/stats"));
  return (await res.json()).chunks_total as number;
}

export async function uploadSpec(
  sessionId: string,
  file: File,
): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await check(
    await fetch(`/api/sessions/${sessionId}/spec/upload`, {
      method: "POST",
      body: form,
    }),
  );
  return (await res.json()).spec_markdown as string;
}
