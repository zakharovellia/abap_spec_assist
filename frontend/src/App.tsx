import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSession,
  deleteSession,
  fetchMe,
  fetchMessages,
  fetchSpec,
  listSessions,
  logout,
  renameSession,
  streamMessage,
  uploadSpec,
  type SessionMeta,
  type SpecSection,
} from "./api";
import ChatPanel, { type ChatMessage } from "./ChatPanel";
import ExamplesPanel from "./ExamplesPanel";
import LoginScreen from "./LoginScreen";
import SessionSidebar from "./SessionSidebar";
import SpecPreview from "./SpecPreview";
import { FileTextIcon, LogOutIcon, MoonIcon, SunIcon } from "./icons";

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
  const [authChecked, setAuthChecked] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [turnStatus, setTurnStatus] = useState<string | null>(null);
  const [spec, setSpec] = useState("");
  const [prevSpec, setPrevSpec] = useState<string | null>(null);
  const [specUpdatedAt, setSpecUpdatedAt] = useState<Date | null>(null);
  const [dragging, setDragging] = useState(false);
  const sessionPromise = useRef<Promise<string> | null>(null);
  const dragDepth = useRef(0);
  const specAtTurnStart = useRef("");
  // Карта id раздела → текст: документ собирается из SSE-дельт (сервер шлёт
  // только изменившиеся разделы, а не весь текст на каждую правку)
  const sectionsRef = useRef<Map<string, string>>(new Map());

  /** Полная замена локальной карты разделов; возвращает markdown документа. */
  function seedSections(sections: SpecSection[]): string {
    sectionsRef.current = new Map(sections.map((s) => [s.id, s.body]));
    return sections
      .map((s) => s.body)
      .filter(Boolean)
      .join("\n\n");
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("tza-theme", theme);
  }, [theme]);

  useEffect(() => {
    fetchMe()
      .then(setUsername)
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!username) return;
    sessionPromise.current = (async () => {
      const list = await listSessions().catch(() => []);
      setSessions(list);
      const created = await createSession();
      setSessions((prev) => [created, ...prev]);
      setSessionId(created.id);
      return created.id;
    })().catch((e) => {
      pushMessage({
        role: "error",
        content: `Нет связи с сервером: ${e.message}`,
      });
      throw e;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username]);

  async function handleLogout() {
    await logout().catch(() => {});
    setUsername(null);
    setSessionId(null);
    sessionPromise.current = null;
    setSessions([]);
    setMessages([]);
    setSpec("");
    setPrevSpec(null);
    sectionsRef.current = new Map();
  }

  function refreshSessions() {
    listSessions()
      .then(setSessions)
      .catch(() => {});
  }

  async function selectSession(id: string) {
    if (id === sessionId || busy) return;
    setSessionId(id);
    sessionPromise.current = Promise.resolve(id);
    setBusy(true);
    setMessages([]);
    setSpec("");
    setPrevSpec(null);
    setSpecUpdatedAt(null);
    sectionsRef.current = new Map();
    try {
      const [specData, history] = await Promise.all([
        fetchSpec(id),
        fetchMessages(id),
      ]);
      seedSections(specData.sections);
      setSpec(specData.spec_markdown);
      setMessages(history.map((m) => ({ ...m, at: new Date() })));
    } catch (e) {
      pushMessage({
        role: "error",
        content: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleNewChat() {
    if (busy) return;
    try {
      const created = await createSession();
      setSessions((prev) => [created, ...prev]);
      await selectSession(created.id);
    } catch (e) {
      pushMessage({
        role: "error",
        content: e instanceof Error ? e.message : String(e),
      });
    }
  }

  async function handleRenameSession(id: string, title: string) {
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
    try {
      await renameSession(id, title);
    } catch {
      refreshSessions();
    }
  }

  async function handleDeleteSession(id: string) {
    const wasActive = id === sessionId;
    setSessions((prev) => prev.filter((s) => s.id !== id));
    try {
      await deleteSession(id);
    } catch {
      refreshSessions();
      return;
    }
    if (wasActive) void handleNewChat();
  }

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

  /** Применить SSE-дельту: order — id всех разделов, changed — новые тела. */
  function applySpecDelta(order: string[], changed: Record<string, string>) {
    const prev = sectionsRef.current;
    const next = new Map<string, string>();
    const parts: string[] = [];
    for (const id of order) {
      const body = changed[id] ?? prev.get(id) ?? "";
      next.set(id, body);
      if (body) parts.push(body);
    }
    sectionsRef.current = next;
    applySpec(parts.join("\n\n"));
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
        onSpec: applySpecDelta,
        onDone: (reply, order) => {
          finalizeLast(reply);
          // расхождение с сервером (пропущенная дельта) — забрать документ целиком
          const map = sectionsRef.current;
          if (order.length !== map.size || order.some((sid) => !map.has(sid))) {
            void fetchSpec(id)
              .then((d) => {
                seedSections(d.sections);
                setSpec(d.spec_markdown);
              })
              .catch(() => {});
          }
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
      refreshSessions();
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
          const data = await uploadSpec(id, file);
          setPrevSpec(null);
          seedSections(data.sections);
          setSpec(data.spec_markdown);
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

  if (!authChecked) return null;

  if (!username) {
    return <LoginScreen onSuccess={setUsername} />;
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
          <ExamplesPanel />
          <button
            className="icon-btn"
            title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
          <button
            className="icon-btn"
            title={`Выйти (${username})`}
            onClick={() => void handleLogout()}
          >
            <LogOutIcon />
          </button>
        </div>
      </header>

      <main className="app-main">
        <SessionSidebar
          sessions={sessions}
          activeId={sessionId}
          disabled={busy}
          onSelect={(id) => void selectSession(id)}
          onNew={() => void handleNewChat()}
          onRename={(id, title) => void handleRenameSession(id, title)}
          onDelete={(id) => void handleDeleteSession(id)}
        />
        <ChatPanel
          messages={messages}
          busy={busy}
          turnStatus={turnStatus}
          onSend={handleSend}
          onUpload={handleUpload}
        />
        <SpecPreview
          sessionId={sessionId}
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
