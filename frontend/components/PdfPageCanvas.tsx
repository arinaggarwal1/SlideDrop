"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Minus, Plus, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";

export interface PdfPageTile {
  id: string;
  path: string;
  filename: string;
  sourceNumber: number;
  page: number;
}

function Preview({ page }: { page: PdfPageTile }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  return failed ? (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-3 text-center text-xs text-muted-foreground">
      <span>Preview unavailable. This page can still be merged.</span>
      <button type="button" className="underline" onClick={() => { setAttempt(attempt + 1); setFailed(false); }}>Retry preview</button>
    </div>
  ) : (
    // Local thumbnails are size-limited and cached by the backend.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={apiUrl(`/pdfs/preview?${new URLSearchParams({ path: page.path, page: String(page.page), retry: String(attempt) })}`)}
      alt={`${page.filename}, page ${page.page}`} loading="lazy" decoding="async" draggable={false}
      className="h-full w-full object-contain" onError={() => setFailed(true)} />
  );
}

export function PdfPageCanvas({ pages, movedIds, onReorder, onReset, disabled }: {
  pages: PdfPageTile[];
  movedIds: ReadonlySet<string>;
  onReorder: (ids: string[], movedId: string) => void;
  onReset: () => void;
  disabled: boolean;
}) {
  const [width, setWidth] = useState(180);
  const [dragged, setDragged] = useState<string | null>(null);
  const [target, setTarget] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  function move(id: string, to: number) {
    const from = pages.findIndex(page => page.id === id);
    if (disabled || from < 0 || from === to || to < 0 || to >= pages.length) return;
    const ids = pages.map(page => page.id);
    ids.splice(from, 1);
    ids.splice(to, 0, id);
    onReorder(ids, id);
    setAnnouncement(`Page moved to position ${to + 1} of ${pages.length}.`);
  }
  return (
    <section className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm" aria-label="Page order">
      <div className="sticky top-0 z-10 mb-5 flex flex-wrap items-center justify-between gap-4 border-b border-border bg-card py-3">
        <div><h2 className="text-xl font-semibold">Arrange pages</h2>
          <p className="mt-1 text-sm text-muted-foreground">Drag pages into their final order, or use the arrows below each preview.</p>
          <p className="mt-1 text-xs text-muted-foreground">A subtle red outline marks pages you moved. Pages that just shift to make room stay unmarked.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onReset} disabled={disabled}><RotateCcw className="h-4 w-4" />Reset order</Button>
          <Button variant="outline" size="icon" aria-label="Smaller page previews" disabled={width <= 120} onClick={() => setWidth(Math.max(120, width - 40))}><Minus /></Button>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Preview size
            <input aria-label="Page preview size" type="range" min="120" max="480" step="20" value={width} onChange={event => setWidth(Number(event.target.value))} className="w-28 accent-primary" />
          </label>
          <Button variant="outline" size="icon" aria-label="Larger page previews" disabled={width >= 480} onClick={() => setWidth(Math.min(480, width + 40))}><Plus /></Button>
        </div>
      </div>
      <p className="sr-only" role="status">{announcement}</p>
      <div className="grid items-start gap-4" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(min(100%, ${width}px), 1fr))` }}>
        {pages.map((page, index) => (
          <article key={page.id} draggable={!disabled} data-moved={movedIds.has(page.id) || undefined} aria-label={`Position ${index + 1}, PDF ${page.sourceNumber}, page ${page.page}${movedIds.has(page.id) ? ", moved from its default order" : ""}`}
            onDragStart={event => { setDragged(page.id); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", page.id); }}
            onDragEnd={() => { setDragged(null); setTarget(null); }}
            onDragOver={event => { if (dragged && !disabled) { event.preventDefault(); setTarget(page.id); } }}
            onDrop={event => { event.preventDefault(); if (dragged) move(dragged, index); setDragged(null); setTarget(null); }}
            className={`min-w-0 rounded-xl border-2 p-2 ${target === page.id && dragged !== page.id ? "border-primary" : movedIds.has(page.id) ? "border-rose-400/45 dark:border-rose-400/35" : "border-transparent"} ${movedIds.has(page.id) ? "bg-rose-500/[0.035]" : ""} ${dragged === page.id ? "opacity-40" : ""} ${disabled ? "" : "cursor-grab active:cursor-grabbing"}`}>
            <div className="relative aspect-[3/4] overflow-hidden rounded-lg border border-border bg-muted/30">
              <Preview page={page} />
              <span title={`PDF ${page.sourceNumber}: ${page.filename}`} className="absolute right-2 top-2 max-w-[calc(100%-1rem)] truncate rounded-md border border-border bg-background/95 px-2 py-1 text-xs font-semibold shadow-sm">PDF {page.sourceNumber}</span>
            </div>
            <p title={page.filename} className="mt-2 truncate text-xs font-medium">{page.filename}</p>
            <p className="mt-1 text-xs text-muted-foreground">Page {page.page} · Position {index + 1}</p>
            <div className="mt-1 h-5">
              {movedIds.has(page.id) && <span title="You moved this page out of its default order. Return it to its original place or reset order to clear the highlight." className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-medium text-rose-700 dark:text-rose-300"><span aria-hidden="true" className="h-1 w-1 rounded-full bg-current" />Moved</span>}
            </div>
            <div className="mt-2 flex gap-1">
              <Button variant="outline" size="sm" className="flex-1" disabled={disabled || index === 0} aria-label={`Move position ${index + 1} earlier`} onClick={() => move(page.id, index - 1)}><ArrowLeft className="h-3 w-3" /></Button>
              <Button variant="outline" size="sm" className="flex-1" disabled={disabled || index === pages.length - 1} aria-label={`Move position ${index + 1} later`} onClick={() => move(page.id, index + 1)}><ArrowRight className="h-3 w-3" /></Button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
