import { useState } from "react";
import { createDocument, startGeneration, type Scenario } from "../api/client";

export function ScenarioStart({ onStarted }: { onStarted: (docId: string) => void }) {
  const [scenario, setScenario] = useState<Scenario>("new");
  const [parentObject, setParentObject] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const legacyMissing = scenario === "modification";

  async function start() {
    setBusy(true);
    try {
      const doc = await createDocument({
        author_id: "current_user",
        tz_type: "alv_report",
        scenario,
        title: description.slice(0, 120),
        parent_object_ref: parentObject || undefined,
      });
      await startGeneration(doc.id, description);
      onStarted(doc.id);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ margin: "auto", width: 560, padding: 24, border: "1px solid #ddd" }}>
      <h2>Создать ТЗ</h2>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input
          type="radio"
          checked={scenario === "new"}
          onChange={() => setScenario("new")}
        />{" "}
        Новая разработка
      </label>
      <label style={{ display: "block", marginBottom: 16 }}>
        <input
          type="radio"
          checked={scenario === "modification"}
          onChange={() => setScenario("modification")}
        />{" "}
        Доработка существующего объекта
      </label>

      {scenario === "modification" && (
        <div style={{ marginBottom: 16 }}>
          <label>Объект SAP (программа / ФМ / транзакция / класс):</label>
          <input
            style={{ width: "100%", padding: 6 }}
            placeholder="ZRM_REPORT_01"
            value={parentObject}
            onChange={(e) => setParentObject(e.target.value)}
          />
          {legacyMissing && (
            <p style={{ color: "#b8860b", fontSize: 13 }}>
              ⚠ Без приложения старого ТЗ описание текущего поведения будет
              реконструировано только из кода.
            </p>
          )}
        </div>
      )}

      <label>Опишите требования / изменения:</label>
      <textarea
        style={{ width: "100%", height: 120, padding: 6 }}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />

      <button
        style={{ marginTop: 16, padding: "8px 24px" }}
        disabled={busy || !description}
        onClick={start}
      >
        {busy ? "Запуск..." : "Начать →"}
      </button>
    </div>
  );
}
