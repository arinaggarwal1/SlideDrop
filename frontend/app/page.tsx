"use client";

import type { ReactNode } from "react";
import { useCallback, useState } from "react";
import Image from "next/image";
import { ArrowUpRight, FileImage, FileStack, FileText, ShieldCheck } from "lucide-react";

import { ExtractionEnginePanel } from "@/components/ExtractionEnginePanel";
import { FinishedView } from "@/components/FinishedView";
import { MergePdfWorkspace } from "@/components/MergePdfWorkspace";
import { ProcessingView } from "@/components/ProcessingView";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadZone } from "@/components/UploadZone";
import { Button } from "@/components/ui/button";
import { AppUpdateControl } from "@/components/AppUpdateControl";

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
  kind,
  onClick,
}: {
  title: string;
  description: string;
  actionLabel: string;
  icon: ReactNode;
  kind: "convert" | "merge" | "extract";
  onClick: () => void;
}) {
  return (
    <button type="button" className="home-tool" data-tool={kind} onClick={onClick} aria-label={actionLabel}>
      <span className="home-tool-art" aria-hidden="true">
        <span className="home-paper home-paper-back" />
        <span className="home-paper home-paper-front">{icon}<span className="home-paper-line" /><span className="home-paper-line short" /></span>
      </span>
      <span className="home-tool-copy">
        <span role="heading" aria-level={2} className="home-tool-title">{title}</span>
        <span className="home-tool-description">{description}</span>
      </span>
      <span className="home-tool-action">{actionLabel}<ArrowUpRight aria-hidden="true" className="h-4 w-4" /></span>
    </button>
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
    <div className={`${appState === "home" ? "home-shell" : "min-h-screen"} bg-[linear-gradient(180deg,rgba(250,251,255,1),rgba(245,247,250,1))] dark:bg-[linear-gradient(180deg,rgba(15,18,27,1),rgba(12,15,22,1))]`}>
      <header className={appState === "home" ? "home-header" : "border-b border-border/50 px-6 py-4"}>
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted">
              <Image
                src="/icon.png"
                alt=""
                width={36}
                height={36}
                className="h-9 w-9"
                priority
              />
            </div>
            <div>
              <span className="block text-lg font-semibold tracking-tight text-foreground">
                SlideDrop
              </span>
              <span className="text-xs text-muted-foreground">
                {appState === "home" ? "Your document workspace" : "Slide conversion and PDF assembly, fully local."}
              </span>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className={appState === "home" ? "home-main" : "px-6 py-12"}>
        <div className={`mx-auto w-full ${containerClass}`}>
          {appState === "home" && (
            <div className="home-content">
              <div className="home-intro">
                <p className="home-eyebrow">YOUR EVERYDAY TOOLKIT</p>
                <h1>
                  Your documents. <span>In good order.</span>
                </h1>
                <p className="home-subtitle">
                  Turn slides into images, put PDFs in order, and prepare your next extraction.
                </p>
              </div>

              <div className="home-tools">
                <ToolCard
                  title="Slides to Images"
                  description="Turn your slide deck into crisp, ready-to-use images."
                  actionLabel="Open Converter"
                  kind="convert"
                  icon={<FileImage className="h-6 w-6" />}
                  onClick={handleSelectConvert}
                />
                <ToolCard
                  title="PDF Workspace"
                  description="Bring files together. Arrange every page just how you want it."
                  actionLabel="Open PDF Workspace"
                  kind="merge"
                  icon={<FileStack className="h-6 w-6" />}
                  onClick={handleSelectMerge}
                />
                <ToolCard
                  title="Extraction Engine"
                  description="Shape your extraction prompt around the subject at hand."
                  actionLabel="Open Extraction Engine"
                  kind="extract"
                  icon={<FileText className="h-6 w-6" />}
                  onClick={() => handleSelectPromptBuilder()}
                />
              </div>
              <footer className="home-footer">
                <span className="home-privacy"><ShieldCheck aria-hidden="true" className="h-4 w-4" />Your documents stay on your device.</span>
                <AppUpdateControl />
              </footer>
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

      {appState !== "home" && <footer className="border-t border-border/50 px-6 py-4 text-center">
        <p className="text-xs text-muted-foreground">
          SlideDrop keeps conversion and PDF merge workflows local to your machine.
        </p>
      </footer>}
    </div>
  );
}
