import { useEffect, useRef, useState } from "react";
import type { SessionMeta } from "./api";
import { MessageSquareIcon, PencilIcon, PlusIcon, TrashIcon } from "./icons";

interface Props {
  sessions: SessionMeta[];
  activeId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}

function fmtDate(epochSeconds: number) {
  const d = new Date(epochSeconds * 1000);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay
    ? d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

export default function SessionSidebar({
  sessions,
  activeId,
  disabled,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId) editRef.current?.focus();
  }, [editingId]);

  function startEdit(s: SessionMeta) {
    setEditingId(s.id);
    setDraft(s.title);
  }

  function commitEdit() {
    const title = draft.trim();
    if (editingId && title) onRename(editingId, title);
    setEditingId(null);
  }

  return (
    <aside className="sidebar panel">
      <button className="sidebar-new" onClick={onNew} disabled={disabled}>
        <PlusIcon size={16} />
        Новое ТЗ
      </button>

      <div className="sidebar-list">
        {sessions.length === 0 && (
          <div className="sidebar-empty">Пока нет сохранённых ТЗ</div>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`sidebar-item ${s.id === activeId ? "active" : ""}`}
            onClick={() => editingId !== s.id && onSelect(s.id)}
          >
            <MessageSquareIcon size={15} className="sidebar-item-icon" />
            {editingId === s.id ? (
              <input
                ref={editRef}
                className="sidebar-item-input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitEdit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitEdit();
                  if (e.key === "Escape") setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span className="sidebar-item-title">{s.title}</span>
            )}
            <span className="sidebar-item-time">{fmtDate(s.updated_at)}</span>
            <div className="sidebar-item-actions">
              <button
                className="sidebar-item-btn"
                title="Переименовать"
                onClick={(e) => {
                  e.stopPropagation();
                  startEdit(s);
                }}
              >
                <PencilIcon size={13} />
              </button>
              <button
                className="sidebar-item-btn"
                title="Удалить"
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Удалить «${s.title}»?`)) onDelete(s.id);
                }}
              >
                <TrashIcon size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
