import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { diffArrays, diffLines } from "diff";
import { CheckIcon, CopyIcon, DownloadIcon, FileTextIcon } from "./icons";

interface Props {
  markdown: string;
  prevMarkdown: string | null;
  updatedAt: Date | null;
}

type ViewMode = "doc" | "diff";

function splitBlocks(md: string): string[] {
  return md
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);
}

export default function SpecPreview({ markdown, prevMarkdown, updatedAt }: Props) {
  const [copied, setCopied] = useState(false);
  const [flash, setFlash] = useState(false);
  const [mode, setMode] = useState<ViewMode>("doc");
  const firstRender = useRef(true);

  const hasDiff = prevMarkdown !== null && prevMarkdown !== markdown;

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    if (!markdown) return;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 1600);
    return () => clearTimeout(t);
  }, [markdown]);

  useEffect(() => {
    if (!hasDiff) setMode("doc");
  }, [hasDiff]);

  /* Документ: блоки, добавленные/изменённые в последней правке, подсвечиваются */
  const blocks = useMemo(() => {
    const current = splitBlocks(markdown);
    if (!hasDiff) return current.map((text) => ({ text, added: false }));
    const parts = diffArrays(splitBlocks(prevMarkdown!), current);
    const out: { text: string; added: boolean }[] = [];
    for (const part of parts) {
      if (part.removed) continue;
      for (const text of part.value) out.push({ text, added: !!part.added });
    }
    return out;
  }, [markdown, prevMarkdown, hasDiff]);

  /* Режим «Изменения»: построчный дифф */
  const diffParts = useMemo(
    () =>
      hasDiff
        ? diffLines(prevMarkdown!.trimEnd() + "\n", markdown.trimEnd() + "\n")
        : [],
    [markdown, prevMarkdown, hasDiff],
  );

  function download() {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tz.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function copy() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const words = markdown ? markdown.trim().split(/\s+/).length : 0;

  return (
    <section className="preview panel">
      <div className="preview-toolbar">
        <div className="preview-title">
          <h2>Документ ТЗ</h2>
          {markdown ? (
            <span className={`status-pill ${flash ? "status-flash" : ""}`}>
              {flash
                ? "обновлено"
                : updatedAt
                  ? `сохранено в ${updatedAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`
                  : "черновик"}
            </span>
          ) : (
            <span className="status-pill status-empty">пусто</span>
          )}
        </div>
        <div className="preview-actions">
          {hasDiff && (
            <div className="segmented" role="tablist">
              <button
                role="tab"
                aria-selected={mode === "doc"}
                className={mode === "doc" ? "active" : ""}
                onClick={() => setMode("doc")}
              >
                Документ
              </button>
              <button
                role="tab"
                aria-selected={mode === "diff"}
                className={mode === "diff" ? "active" : ""}
                onClick={() => setMode("diff")}
              >
                Изменения
              </button>
            </div>
          )}
          {markdown && <span className="word-count">{words} слов</span>}
          <button
            className="icon-btn"
            title="Скопировать Markdown"
            disabled={!markdown}
            onClick={copy}
          >
            {copied ? <CheckIcon className="icon-ok" /> : <CopyIcon />}
          </button>
          <button
            className="icon-btn"
            title="Скачать .md"
            disabled={!markdown}
            onClick={download}
          >
            <DownloadIcon />
          </button>
        </div>
      </div>

      <div className="preview-scroll">
        {!markdown ? (
          <div className="preview-empty">
            <div className="preview-empty-icon">
              <FileTextIcon size={30} />
            </div>
            <h3>Документ появится здесь</h3>
            <p>
              Приложите существующее ТЗ или опишите задачу в чате — превью
              будет обновляться после каждого шага.
            </p>
          </div>
        ) : mode === "doc" ? (
          <article className={`paper ${flash ? "paper-flash" : ""}`}>
            {blocks.map((b, i) => (
              <div key={i} className={b.added ? "block-added" : undefined}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {b.text}
                </ReactMarkdown>
              </div>
            ))}
          </article>
        ) : (
          <article className="paper paper-diff">
            <pre className="diff-view">
              {diffParts.map((part, i) => (
                <span
                  key={i}
                  className={
                    part.added
                      ? "diff-added"
                      : part.removed
                        ? "diff-removed"
                        : "diff-context"
                  }
                >
                  {part.value}
                </span>
              ))}
            </pre>
          </article>
        )}
      </div>
    </section>
  );
}
