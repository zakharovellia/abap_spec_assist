import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BotMark,
  FileTextIcon,
  PaperclipIcon,
  SendIcon,
  SparklesIcon,
} from "./icons";

export interface ChatMessage {
  role: "user" | "assistant" | "error" | "file";
  content: string;
  at: Date;
  streaming?: boolean;
}

interface Props {
  messages: ChatMessage[];
  busy: boolean;
  turnStatus: string | null;
  onSend: (text: string) => void;
  onUpload: (file: File) => void;
}

const SUGGESTIONS = [
  "Составь ТЗ на ALV-отчёт по заказам на поставку",
  "Нужна доработка печатной формы счёта-фактуры",
  "ТЗ на расширение BAdI при проведении документа",
];

function fmtTime(d: Date) {
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

export default function ChatPanel({
  messages,
  busy,
  turnStatus,
  onSend,
  onUpload,
}: Props) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [draft]);

  function submit() {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    onSend(text);
  }

  const empty = messages.length === 0;

  return (
    <section className="chat panel">
      <div className="chat-messages" ref={listRef}>
        {empty && (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <SparklesIcon size={26} />
            </div>
            <h2>Помогу написать ТЗ для ABAP-разработчика</h2>
            <p>
              Приложите существующее ТЗ — я разберу его и внесу доработки. Или
              начнём с чистого листа: опишите задачу своими словами.
            </p>
            <div className="chat-suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} disabled={busy} onClick={() => onSend(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          if (m.role === "file") {
            return (
              <div key={i} className="msg-row msg-row-user">
                <div className="file-chip">
                  <FileTextIcon size={16} />
                  <span>{m.content}</span>
                </div>
              </div>
            );
          }
          if (m.role === "error") {
            return (
              <div key={i} className="msg-error">
                {m.content}
              </div>
            );
          }
          const isUser = m.role === "user";
          // стримящееся сообщение без единого токена — индикатор «печатает»
          if (m.streaming && !m.content) {
            return (
              <div key={i} className="msg-row msg-row-assistant">
                <div className="avatar" aria-hidden>
                  <BotMark size={16} />
                </div>
                <div className="msg-col">
                  {turnStatus ? (
                    <div className="spec-updating-chip">
                      <span className="spinner" /> {turnStatus}
                    </div>
                  ) : (
                    <div
                      className="msg msg-assistant msg-typing"
                      aria-label="Ассистент печатает"
                    >
                      <span />
                      <span />
                      <span />
                    </div>
                  )}
                </div>
              </div>
            );
          }
          return (
            <div
              key={i}
              className={`msg-row ${isUser ? "msg-row-user" : "msg-row-assistant"}`}
            >
              {!isUser && (
                <div className="avatar" aria-hidden>
                  <BotMark size={16} />
                </div>
              )}
              <div className="msg-col">
                <div
                  className={`msg ${isUser ? "msg-user" : "msg-assistant"} ${
                    m.streaming ? "msg-streaming" : ""
                  }`}
                >
                  {isUser ? (
                    <p className="msg-plain">{m.content}</p>
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                  )}
                </div>
                {!m.streaming && <span className="msg-time">{fmtTime(m.at)}</span>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="chat-composer">
        <input
          ref={fileRef}
          type="file"
          accept=".docx,.md,.markdown,.txt"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <button
          className="icon-btn composer-attach"
          title="Приложить существующее ТЗ (.docx, .md, .txt)"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
        >
          <PaperclipIcon />
        </button>
        <textarea
          ref={taRef}
          value={draft}
          placeholder="Опишите задачу или доработку…"
          rows={1}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button
          className="send-btn"
          title="Отправить (Enter)"
          disabled={busy || !draft.trim()}
          onClick={submit}
        >
          <SendIcon />
        </button>
      </div>
    </section>
  );
}
