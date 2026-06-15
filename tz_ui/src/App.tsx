import { useState } from "react";
import { ScenarioStart } from "./components/ScenarioStart";
import { ChatWorkspace } from "./components/ChatWorkspace";

export function App() {
  const [activeDocId, setActiveDocId] = useState<string | null>(null);

  return (
    <div style={{ fontFamily: "sans-serif", height: "100vh", display: "flex" }}>
      {activeDocId ? (
        <ChatWorkspace docId={activeDocId} onBack={() => setActiveDocId(null)} />
      ) : (
        <ScenarioStart onStarted={setActiveDocId} />
      )}
    </div>
  );
}
