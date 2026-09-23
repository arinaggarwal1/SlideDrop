"use client";

import type { ReactNode } from "react";
import { useCallback, useState } from "react";
import { FileImage, FileStack, FileText, Layers } from "lucide-react";

import { ExtractionEnginePanel } from "@/components/ExtractionEnginePanel";
import { FinishedView } from "@/components/FinishedView";
import { MergePdfWorkspace } from "@/components/MergePdfWorkspace";
import { ProcessingView } from "@/components/ProcessingView";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadZone } from "@/components/UploadZone";
import { Button } from "@/components/ui/button";

type AppState =
  | "home"
  | "convert"
  | "merge"
  | "promptBuilder"
  | "processing"
  | "finished"
  | "error";

interface FileInfo {
  jobId: string;
  filename: string;
  fileType: string;
  pageCount: number;
  customOutputFolder?: string;
  extractText?: boolean;
  parallelism?: number;
  modelChoice?: "3b" | "7b";
}

function ToolCard({
  title,
  description,
  actionLabel,
  icon,
  onClick,
}: {
  title: string;
  description: string;
  actionLabel: string;
  icon: ReactNode;
  onClick: () => void;
}) {
  return (
    <div className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(250,251,255,0.94))] p-6 shadow-sm transition-colors duration-200 hover:border-primary/30 dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
          </div>
          <div className="rounded-xl bg-muted p-3 text-primary">{icon}</div>
        </div>

        <p className="mt-3 flex-1 text-sm leading-6 text-muted-foreground">{description}</p>

        <Button
          className="mt-5 h-10 rounded-xl cursor-pointer justify-start px-4"
          onClick={onClick}
        >
          {actionLabel}
        </Button>
      </div>
    </div>
  );
}

export default function Home() {
  const [appState, setAppState] = useState<AppState>("home");
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [outputFolder, setOutputFolder] = useState("");
  const [extractionFile, setExtractionFile] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [promptBuilderSourceFolder, setPromptBuilderSourceFolder] = useState<string | undefined>();

  const handleFileUploaded = useCallback((data: FileInfo) => {
    setFileInfo(data);
    setAppState("processing");
  }, []);

  const handleError = useCallback((message: string | unknown) => {
    const msg = typeof message === "string" ? message : String(message);
    setErrorMessage(msg);
    setAppState("error");
  }, []);

  const handleConversionComplete = useCallback((folder: string, extFile?: string) => {
    setOutputFolder(folder);
    if (extFile) {
      setExtractionFile(extFile);
    }
    setAppState("finished");
  }, []);

  const handleSelectConvert = useCallback(() => {
    setErrorMessage("");
    setAppState("convert");
  }, []);

  const handleSelectMerge = useCallback(() => {
    setErrorMessage("");
    setAppState("merge");
  }, []);

  const handleSelectPromptBuilder = useCallback((sourceFolder?: string) => {
    setErrorMessage("");
    setPromptBuilderSourceFolder(sourceFolder);
    setAppState("promptBuilder");
  }, []);

  const handleBackHome = useCallback(() => {
    setFileInfo(null);
    setOutputFolder("");
    setExtractionFile("");
    setErrorMessage("");
    setPromptBuilderSourceFolder(undefined);
    setAppState("home");
  }, []);

  const handleConvertAnother = useCallback(() => {
    setFileInfo(null);
    setOutputFolder("");
    setExtractionFile("");
    setErrorMessage("");
    setPromptBuilderSourceFolder(undefined);
    setAppState("convert");
  }, []);

  const containerClass =
    appState === "merge" || appState === "home" || appState === "promptBuilder"
      ? "max-w-6xl"
      : "max-w-2xl";

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,rgba(250,251,255,1),rgba(245,247,250,1))] dark:bg-[linear-gradient(180deg,rgba(15,18,27,1),rgba(12,15,22,1))]">
      <header className="border-b border-border/50 px-6 py-4">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-primary p-2 text-primary-foreground">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <span className="block text-lg font-semibold tracking-tight text-foreground">
                SlideDrop
              </span>
              <span className="text-xs text-muted-foreground">
                Slide conversion and PDF assembly, fully local.
              </span>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="px-6 py-12">
        <div className={`mx-auto w-full ${containerClass}`}>
          {appState === "home" && (
            <div className="animate-fade-in-up">
              <div className="mx-auto max-w-3xl text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                  Choose what you want to do
                </h1>
                <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
                  Use the converter for a single slide deck, or open the PDF workspace to combine files, reorder them, and choose which pages to keep.
                </p>
              </div>

              <div className="mt-8 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                <ToolCard
                  title="Slides to Images"
                  description="Upload one PowerPoint or PDF and export each slide as a PNG. You can also save to a custom folder or extract text locally."
                  actionLabel="Open Converter"
                  icon={<FileImage className="h-6 w-6" />}
                  onClick={handleSelectConvert}
                />
                <ToolCard
                  title="PDF Workspace"
                  description="Choose several PDFs, set page ranges for each one, drag them into order, and save the merged file with the native folder picker."
                  actionLabel="Open Merge Workspace"
                  icon={<FileStack className="h-6 w-6" />}
                  onClick={handleSelectMerge}
                />
                <ToolCard
                  title="Extraction Engine"
                  description="Start from the exact lecture prompt you already use, then generate a domain-adapted version locally with Ollama without changing the rest of your workflow."
                  actionLabel="Open Extraction Engine"
                  icon={<FileText className="h-6 w-6" />}
                  onClick={() => handleSelectPromptBuilder()}
                />
              </div>
            </div>
          )}

          {appState === "convert" && (
            <div className="animate-fade-in-up">
              <div className="mb-10 text-center">
                <button
                  type="button"
                  onClick={handleBackHome}
                  className="mb-5 inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  Back to tools
                </button>
                <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                  Convert slides to images
                </h1>
                <p className="mx-auto mt-3 max-w-md text-base text-muted-foreground">
                  Upload one PowerPoint or PDF and export every slide as a high-quality PNG image.
                </p>
              </div>
              <UploadZone onFileUploaded={handleFileUploaded} onError={handleError} />
            </div>
          )}

          {appState === "merge" && <MergePdfWorkspace onBack={handleBackHome} />}

          {appState === "promptBuilder" && (
            <ExtractionEnginePanel
              onBack={handleBackHome}
              sourceOutputFolder={promptBuilderSourceFolder}
            />
          )}

          {appState === "processing" && fileInfo && (
            <ProcessingView
              jobId={fileInfo.jobId}
              customOutputFolder={fileInfo.customOutputFolder}
              extractText={fileInfo.extractText}
              parallelism={fileInfo.parallelism}
              modelChoice={fileInfo.modelChoice}
              onComplete={handleConversionComplete}
              onError={handleError}
            />
          )}

          {appState === "finished" && (
            <div className="animate-fade-in-up">
              <div className="mb-6 text-center">
                <button
                  type="button"
                  onClick={handleBackHome}
                  className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  Back to tools
                </button>
              </div>
              <FinishedView
                outputFolder={outputFolder}
                extractionFile={extractionFile}
                onBuildExtractionPrompt={() => handleSelectPromptBuilder(outputFolder)}
                onConvertAnother={handleConvertAnother}
              />
            </div>
          )}

          {appState === "error" && (
            <div className="animate-fade-in-up mx-auto w-full max-w-lg">
              <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center">
                <div className="mx-auto mb-4 w-fit rounded-full bg-destructive/10 p-3">
                  <svg
                    className="h-6 w-6 text-destructive"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="15" y1="9" x2="9" y2="15" />
                    <line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                </div>
                <h3 className="mb-2 text-lg font-semibold text-foreground">Something went wrong</h3>
                <p className="mb-6 whitespace-pre-wrap text-sm text-muted-foreground">
                  {errorMessage}
                </p>
                <div className="flex justify-center gap-3">
                  <Button variant="outline" className="cursor-pointer" onClick={handleBackHome}>
                    Back to Tools
                  </Button>
                  <Button className="cursor-pointer" onClick={handleSelectConvert}>
                    Try Converter Again
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="border-t border-border/50 px-6 py-4 text-center">
        <p className="text-xs text-muted-foreground">
          SlideDrop keeps conversion and PDF merge workflows local to your machine.
        </p>
      </footer>
    </div>
  );
}
