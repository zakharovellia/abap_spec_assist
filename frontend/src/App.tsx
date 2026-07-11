import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSession,
  fetchExamplesStats,
  streamMessage,
  uploadSpec,
} from "./api";
import ChatPanel, { type ChatMessage } from "./ChatPanel";
import SpecPreview from "./SpecPreview";
import { FileTextIcon, MoonIcon, SunIcon } from "./icons";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  const saved = localStorage.getItem("tza-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

const ACCEPTED = [".docx", ".md", ".markdown", ".txt"];

export default function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [turnStatus, setTurnStatus] = useState<string | null>(null);
  const [spec, setSpec] = useState("");
  const [prevSpec, setPrevSpec] = useState<string | null>(null);
  const [specUpdatedAt, setSpecUpdatedAt] = useState<Date | null>(null);
  const [examplesCount, setExamplesCount] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const sessionPromise = useRef<Promise<string> | null>(null);
  const dragDepth = useRef(0);
  const specAtTurnStart = useRef("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("tza-theme", theme);
  }, [theme]);

  useEffect(() => {
    sessionPromise.current = createSession()
      .then((id) => {
        setSessionId(id);
        return id;
      })
      .catch((e) => {
        pushMessage({
          role: "error",
          content: `Нет связи с сервером: ${e.message}`,
        });
        throw e;
      });
    fetchExamplesStats()
      .then(setExamplesCount)
      .catch(() => setExamplesCount(null));
  }, []);

  function pushMessage(msg: Omit<ChatMessage, "at">) {
    setMessages((m) => [...m, { ...msg, at: new Date() }]);
  }

  /** Дописать текст в последнее (стримящееся) сообщение ассистента. */
  function appendToLast(text: string) {
    setMessages((m) => {
      const last = m[m.length - 1];
      if (!last || last.role !== "assistant" || !last.streaming) return m;
      return [...m.slice(0, -1), { ...last, content: last.content + text }];
    });
  }

  function finalizeLast(reply: string) {
    setMessages((m) => {
      const last = m[m.length - 1];
      if (!last || last.role !== "assistant" || !last.streaming) return m;
      return [
        ...m.slice(0, -1),
        { ...last, content: reply || last.content, streaming: false },
      ];
    });
  }

  function applySpec(markdown: string) {
    // первое создание документа — сравнивать не с чем, дифф не показываем
    setPrevSpec(specAtTurnStart.current || null);
    setSpec(markdown);
    setSpecUpdatedAt(new Date());
    setTurnStatus(null);
  }

  async function runTurn(text: string) {
    setBusy(true);
    specAtTurnStart.current = spec;
    pushMessage({ role: "assistant", content: "", streaming: true });
    try {
      const id = sessionId ?? (await sessionPromise.current!);
      await streamMessage(id, text, {
        onToken: (t) => {
          setTurnStatus(null);
          appendToLast(t);
        },
        onStatus: (value, tool) =>
          setTurnStatus(
            value === "updating_spec"
              ? "Обновляю документ…"
              : `Смотрю в SAP: ${tool ?? "объекты"}…`,
          ),
        onSpec: applySpec,
        onDone: (reply, specMarkdown) => {
          finalizeLast(reply);
          if (specMarkdown !== spec && specMarkdown) setSpec(specMarkdown);
        },
      });
    } catch (e) {
      // убрать пустой placeholder, если стрим упал до первого токена
      setMessages((m) =>
        m[m.length - 1]?.streaming && !m[m.length - 1].content
          ? m.slice(0, -1)
          : m,
      );
      pushMessage({
        role: "error",
        content: e instanceof Error ? e.message : String(e),
      });
    } finally {
      finalizeLast("");
      setTurnStatus(null);
      setBusy(false);
    }
  }

  function handleSend(text: string) {
    pushMessage({ role: "user", content: text });
    void runTurn(text);
  }

  const handleUpload = useCallback(
    (file: File) => {
      if (!ACCEPTED.some((ext) => file.name.toLowerCase().endsWith(ext))) {
        pushMessage({
          role: "error",
          content: `Формат не поддерживается: ${file.name}. Нужен .docx, .md или .txt.`,
        });
        return;
      }
      pushMessage({ role: "file", content: file.name });
      void (async () => {
        setBusy(true);
        try {
          const id = sessionId ?? (await sessionPromise.current!);
          const markdown = await uploadSpec(id, file);
          setPrevSpec(null);
          setSpec(markdown);
          setSpecUpdatedAt(new Date());
          await runTurn(
            `Я приложил существующее ТЗ «${file.name}» — оно уже загружено в документ. ` +
              "Кратко опиши, о чём оно, и спроси, какие доработки нужны.",
          );
        } catch (e) {
          pushMessage({
            role: "error",
            content: e instanceof Error ? e.message : String(e),
          });
          setBusy(false);
        }
      })();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, spec],
  );

  function onDragEnter(e: React.DragEvent) {
    e.preventDefault();
    if (!e.dataTransfer.types.includes("Files")) return;
    dragDepth.current += 1;
    setDragging(true);
  }

  function onDragLeave(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && !busy) handleUpload(file);
  }

  return (
    <div
      className="app"
      onDragEnter={onDragEnter}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark">
            <FileTextIcon size={20} />
          </div>
          <div className="brand-text">
            <h1>ТЗ Ассистент</h1>
            <span>SAP → ABAP · технические задания</span>
          </div>
        </div>
        <div className="header-actions">
          {examplesCount !== null && (
            <div
              className="stats-pill"
              title="Фрагментов реальных ТЗ в базе стиля (RAG)"
            >
              <span className="stats-dot" />
              База примеров: {examplesCount}
            </div>
          )}
          <button
            className="icon-btn"
            title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      <main className="app-main">
        <ChatPanel
          messages={messages}
          busy={busy}
          turnStatus={turnStatus}
          onSend={handleSend}
          onUpload={handleUpload}
        />
        <SpecPreview
          markdown={spec}
          prevMarkdown={prevSpec}
          updatedAt={specUpdatedAt}
        />
      </main>

      {dragging && (
        <div className="drop-overlay">
          <div className="drop-card">
            <FileTextIcon size={40} />
            <strong>Отпустите, чтобы приложить ТЗ</strong>
            <span>.docx · .md · .txt</span>
          </div>
        </div>
      )}
    </div>
  );
}
