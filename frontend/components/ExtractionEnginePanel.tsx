"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, Copy, FileText, FolderOpen, RefreshCcw, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";
import { AUTHORITATIVE_DEFAULT_EXTRACTION_PROMPT } from "@/lib/defaultExtractionPrompt";

interface ExtractionEnginePanelProps {
  onBack: () => void;
  sourceOutputFolder?: string;
}

function getErrorMessage(payload: unknown): string {
  if (typeof payload === "string") {
    return payload;
  }
  if (
    payload &&
    typeof payload === "object" &&
    "message" in payload &&
    typeof payload.message === "string"
  ) {
    return payload.message;
  }
  return "Something went wrong while building the prompt.";
}

async function copyTextExactly(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();

  const copied = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!copied) {
    throw new Error("Clipboard access is not available.");
  }
}

export function ExtractionEnginePanel({
  onBack,
  sourceOutputFolder,
}: ExtractionEnginePanelProps) {
  const [useCase, setUseCase] = useState("");
  const [promptText, setPromptText] = useState(AUTHORITATIVE_DEFAULT_EXTRACTION_PROMPT);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCopying, setIsCopying] = useState(false);
  const [isOpeningFolder, setIsOpeningFolder] = useState(false);
  const [inlineError, setInlineError] = useState("");
  const [inlineStatus, setInlineStatus] = useState("");

  const folderDisplay = useMemo(() => {
    if (!sourceOutputFolder) {
      return "";
    }
    return sourceOutputFolder.split("/").slice(-2).join("/");
  }, [sourceOutputFolder]);

  const handleGenerate = async () => {
    setInlineError("");
    setInlineStatus("");

    if (!useCase.trim()) {
      setInlineError("Describe what you want the extraction engine to be used for.");
      return;
    }

    setIsGenerating(true);
    try {
      const res = await fetch(apiUrl("/prompt-builder/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_case: useCase.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(getErrorMessage(data.detail));
      }

      setPromptText(data.prompt);
      setInlineStatus("Custom prompt generated locally with Ollama.");
    } catch (err) {
      setInlineError(
        err instanceof Error ? err.message : "Failed to generate the custom prompt."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = async () => {
    setInlineError("");
    setInlineStatus("");
    setIsCopying(true);
    try {
      await copyTextExactly(promptText);
      setInlineStatus("Prompt copied exactly as shown.");
    } catch (err) {
      setInlineError(err instanceof Error ? err.message : "Failed to copy the prompt.");
    } finally {
      setIsCopying(false);
    }
  };

  const handleReset = () => {
    setPromptText(AUTHORITATIVE_DEFAULT_EXTRACTION_PROMPT);
    setInlineError("");
    setInlineStatus("Reset to the authoritative default prompt.");
  };

  const handleOpenFolder = async () => {
    if (!sourceOutputFolder) {
      return;
    }

    setInlineError("");
    setInlineStatus("");
    setIsOpeningFolder(true);
    try {
      const res = await fetch(apiUrl("/open-location"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: sourceOutputFolder }),
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(getErrorMessage(data?.detail));
      }
    } catch (err) {
      setInlineError(err instanceof Error ? err.message : "Failed to open the slide image folder.");
    } finally {
      setIsOpeningFolder(false);
    }
  };

  return (
    <div className="animate-fade-in-up w-full">
      <div className="mb-6">
        <button
          type="button"
          onClick={onBack}
          className="mb-4 inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to tools
        </button>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Extraction Engine
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
          Generate a copy-paste extraction prompt for ChatGPT or another AI tool.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.55fr)]">
        <section className="space-y-4">
          {sourceOutputFolder && (
            <div className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.95))] p-5 shadow-sm dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-foreground">Slides are ready</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Your exported slide images are in <span className="font-mono text-foreground">~/{folderDisplay}</span>.
                  </p>
                </div>
                <Button
                  variant="outline"
                  className="h-10 rounded-xl cursor-pointer"
                  onClick={handleOpenFolder}
                  disabled={isOpeningFolder}
                >
                  <FolderOpen className="h-4 w-4" />
                  {isOpeningFolder ? "Opening..." : "Open Folder"}
                </Button>
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.95))] p-5 shadow-sm dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-muted p-3 text-primary">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">Prompt generator</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Describe the extraction use case, then generate a domain-specific prompt that preserves the same rigor as the lecture baseline.
                </p>
              </div>
            </div>

            <div className="mt-5 space-y-2">
              <label htmlFor="use-case" className="text-sm font-medium text-foreground">
                Use case
              </label>
              <textarea
                id="use-case"
                value={useCase}
                onChange={(event) => setUseCase(event.target.value)}
                placeholder="Examples: medical anatomy diagrams, bar exam practice questions, annotated legal exhibits"
                className="min-h-28 w-full rounded-xl border border-input bg-background/90 px-4 py-3 text-sm leading-6 text-foreground ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
              <p className="text-xs text-muted-foreground">
                This only builds the prompt. You still keep your manual workflow of uploading slide images into ChatGPT in batches.
              </p>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <Button
                className="h-10 rounded-xl cursor-pointer"
                onClick={handleGenerate}
                disabled={isGenerating}
              >
                <Sparkles className="h-4 w-4" />
                {isGenerating ? "Generating..." : "Generate Custom Prompt"}
              </Button>
              <Button
                variant="outline"
                className="h-10 rounded-xl cursor-pointer"
                onClick={handleCopy}
                disabled={isCopying}
              >
                <Copy className="h-4 w-4" />
                {isCopying ? "Copying..." : "Copy Prompt"}
              </Button>
              <Button
                variant="outline"
                className="h-10 rounded-xl cursor-pointer"
                onClick={handleReset}
              >
                <RefreshCcw className="h-4 w-4" />
                Reset to Default
              </Button>
            </div>

            {inlineError && (
              <p className="mt-4 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {inlineError}
              </p>
            )}

            {!inlineError && inlineStatus && (
              <p className="mt-4 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
                {inlineStatus}
              </p>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] p-5 shadow-sm dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Prompt editor</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Edit manually if you want. Copy always uses the exact text visible here.
              </p>
            </div>
            <div className="rounded-xl bg-muted p-3 text-primary">
              <FileText className="h-5 w-5" />
            </div>
          </div>

          <textarea
            value={promptText}
            onChange={(event) => setPromptText(event.target.value)}
            spellCheck={false}
            autoCorrect="off"
            autoCapitalize="off"
            wrap="soft"
            className="min-h-[34rem] w-full resize-y rounded-xl border border-input bg-background/95 px-4 py-4 font-mono text-[13px] leading-6 text-foreground ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />
        </section>
      </div>
    </div>
  );
}
