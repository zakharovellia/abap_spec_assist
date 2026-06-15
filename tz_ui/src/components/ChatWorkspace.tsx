import { useEffect, useRef, useState } from "react";
import { openGenerationStream } from "../api/client";

interface AgentEvent {
  event: string;
  node?: string;
  detail?: string;
}

export function ChatWorkspace({ docId, onBack }: { docId: string; onBack: () => void }) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = openGenerationStream(docId, (e) => {
      setEvents((prev) => [...prev, e as AgentEvent]);
    });
    wsRef.current = ws;
    return () => ws.close();
  }, [docId]);

  return (
    <div style={{ display: "flex", width: "100%" }}>
      <div style={{ flex: 1, borderRight: "1px solid #ddd", padding: 16 }}>
        <button onClick={onBack}>← К списку</button>
        <h3>Прогресс агентов</h3>
        <ul>
          {events.map((e, i) => (
            <li key={i}>
              {e.event === "node" ? `▶ ${e.node}` : e.event}
              {e.detail ? `: ${e.detail}` : ""}
            </li>
          ))}
        </ul>
      </div>
      <div style={{ flex: 1, padding: 16 }}>
        <h3>Live-preview ТЗ</h3>
        <p style={{ color: "#888" }}>Документ #{docId}</p>
      </div>
    </div>
  );
}
