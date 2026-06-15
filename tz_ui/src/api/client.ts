export type Scenario = "new" | "modification";

export interface TzDocument {
  id: string;
  author_id: string;
  tz_type: string;
  scenario: string;
  title: string | null;
  parent_object_ref: string | null;
  status: string;
  current_revision: string | null;
  created_at: string;
  updated_at: string;
}

const BASE = "/api";

export async function createDocument(input: {
  author_id: string;
  tz_type: string;
  scenario: Scenario;
  title?: string;
  parent_object_ref?: string;
}): Promise<TzDocument> {
  const resp = await fetch(`${BASE}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!resp.ok) throw new Error("Не удалось создать ТЗ");
  return resp.json();
}

export async function listDocuments(): Promise<TzDocument[]> {
  const resp = await fetch(`${BASE}/documents`);
  if (!resp.ok) throw new Error("Не удалось загрузить список ТЗ");
  return resp.json();
}

export async function startGeneration(docId: string, message: string): Promise<void> {
  await fetch(`${BASE}/documents/${docId}/generation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export function openGenerationStream(
  docId: string,
  onEvent: (event: Record<string, unknown>) => void,
): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(
    `${proto}://${window.location.host}${BASE}/documents/${docId}/generation/stream`,
  );
  ws.onmessage = (msg) => onEvent(JSON.parse(msg.data));
  return ws;
}
