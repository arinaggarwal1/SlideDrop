"use client";

import { useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";

interface UpdateState {
  status: "idle" | "checking" | "current" | "available" | "unavailable" | "downloading" | "ready" | "installing" | "error";
  current_version: string;
  latest_version: string | null;
  message: string;
  progress: number;
  can_install: boolean;
  token: string;
}

export function AppUpdateControl() {
  const [update, setUpdate] = useState<UpdateState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch(apiUrl("/updates/status"), { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(setUpdate).catch(() => {});
    return () => controller.abort();
  }, []);

  const polling = update?.status === "downloading";
  useEffect(() => {
    if (!polling) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const response = await fetch(apiUrl("/updates/status"), { signal: controller.signal });
        if (!response.ok) throw new Error();
        setUpdate(await response.json());
        setError("");
      } catch {
        if (!controller.signal.aborted) setError("Connection interrupted. Reconnecting to the update download…");
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, 1000);
    }
    timer = setTimeout(poll, 1000);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [polling]);

  async function act(action: "check" | "download" | "install") {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/updates/${action}`), {
        method: action === "check" ? "GET" : "POST",
        headers: action === "check" ? undefined : { "X-SlideDrop-Update-Token": update?.token || "" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update SlideDrop.");
      setUpdate(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the update service.");
    } finally {
      setBusy(false);
    }
  }

  const locked = busy || update?.status === "checking" || polling || update?.status === "installing";
  return (
    <section aria-label="App updates" className="mx-auto mt-8 max-w-2xl rounded-xl border border-border bg-card/60 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">SlideDrop{update ? ` v${update.current_version}` : ""}</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" size="sm" disabled={locked || update?.status === "ready"} onClick={() => act("check")}>
            <RefreshCw className={`h-4 w-4 ${busy || update?.status === "checking" ? "animate-spin motion-reduce:animate-none" : ""}`} />
            {busy && update?.status !== "available" && update?.status !== "ready" ? "Checking…" : "Check for update"}
          </Button>
          {update?.status === "available" && update.can_install && (
            <Button size="sm" disabled={busy} onClick={() => act("download")}><Download className="h-4 w-4" />Download v{update.latest_version}</Button>
          )}
          {update?.status === "ready" && <Button size="sm" disabled={busy} onClick={() => act("install")}>Install and restart</Button>}
        </div>
      </div>
      {update?.message && <p role="status" className={`mt-2 text-sm ${update.status === "error" ? "text-destructive" : "text-muted-foreground"}`}>{update.message}</p>}
      {polling && <div className="mt-3 flex items-center gap-3"><progress aria-label="Update download" value={update.progress} max={100} className="h-2 flex-1 accent-primary" /><span className="text-xs text-muted-foreground">{update.progress}%</span></div>}
      {error && <p role="alert" className="mt-2 text-sm text-destructive">{error}</p>}
    </section>
  );
}
