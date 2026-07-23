import { useEffect, useRef, useState } from "react";
import {
  deleteExample,
  listExamples,
  uploadExamples,
  type ExampleDoc,
} from "./api";
import { FileTextIcon, PlusIcon, TrashIcon } from "./icons";

const ACCEPT = ".docx,.md,.markdown,.txt";

/** Пилюля «База примеров» в шапке + выпадающая панель управления базой:
    список проиндексированных ТЗ, загрузка нескольких файлов, удаление. */
export default function ExamplesPanel() {
  const [docs, setDocs] = useState<ExampleDoc[] | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setDocs(await listExamples());
    } catch {
      setDocs(null);
      setNotice("База примеров недоступна");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const chunksTotal = (docs ?? []).reduce((n, d) => n + d.chunks, 0);

  async function handleFiles(list: FileList | null) {
    if (!list?.length || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const results = await uploadExamples([...list]);
      const failed = results.filter((r) => r.error);
      const ok = results.length - failed.length;
      setNotice(
        failed.length
          ? failed.map((f) => `${f.name}: ${f.error}`).join("\n")
          : `Проиндексировано файлов: ${ok}`,
      );
      await refresh();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function handleDelete(doc: ExampleDoc) {
    setNotice(null);
    try {
      await deleteExample(doc.source);
      await refresh();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="examples">
      <button
        className="stats-pill stats-pill-btn"
        title="База примеров реальных ТЗ (образцы стиля для ассистента)"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) void refresh();
        }}
      >
        <span className="stats-dot" />
        База примеров: {docs === null ? "—" : chunksTotal}
      </button>

      {open && (
        <>
          <div className="popover-backdrop" onClick={() => setOpen(false)} />
          <div className="examples-popover" role="dialog">
            <div className="examples-popover-head">
              <strong>Примеры ТЗ</strong>
              <button
                className="icon-btn"
                title="Приложить примеры ТЗ (.docx, .md, .txt) — можно несколько"
                disabled={busy}
                onClick={() => fileInput.current?.click()}
              >
                <PlusIcon />
              </button>
            </div>
            <p className="examples-hint">
              Разделы этих документов ассистент использует как образец стиля.
              Файл с тем же именем заменяет прежнюю версию.
            </p>
            {docs && docs.length > 0 ? (
              <ul className="examples-list">
                {docs.map((d) => (
                  <li key={d.source} className="examples-item">
                    <FileTextIcon size={15} />
                    <span className="examples-name" title={d.source}>
                      {d.name}
                    </span>
                    <span className="examples-chunks">{d.chunks}</span>
                    <button
                      className="icon-btn"
                      title="Удалить из базы"
                      disabled={busy}
                      onClick={() => void handleDelete(d)}
                    >
                      <TrashIcon />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="examples-empty">
                {docs === null
                  ? "База недоступна"
                  : "Пока пусто — приложите готовые ТЗ, чтобы ассистент писал в их стиле."}
              </p>
            )}
            {busy && <p className="examples-notice">Индексирую…</p>}
            {notice && !busy && <p className="examples-notice">{notice}</p>}
          </div>
        </>
      )}

      <input
        hidden
        multiple
        type="file"
        accept={ACCEPT}
        ref={fileInput}
        onChange={(e) => void handleFiles(e.target.files)}
      />
    </div>
  );
}
