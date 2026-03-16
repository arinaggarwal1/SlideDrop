"use client";

import { useState, useCallback } from "react";
import { UploadZone } from "@/components/UploadZone";
import { ProcessingView } from "@/components/ProcessingView";
import { FinishedView } from "@/components/FinishedView";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Layers } from "lucide-react";

type AppState = "upload" | "processing" | "finished" | "error";

interface FileInfo {
  jobId: string;
  filename: string;
  fileType: string;
  pageCount: number;
  customOutputFolder?: string;
}

export default function Home() {
  const [appState, setAppState] = useState<AppState>("upload");
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [outputFolder, setOutputFolder] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const handleFileUploaded = useCallback((data: FileInfo) => {
    setFileInfo(data);
    setAppState("processing");
  }, []);

  const handleError = useCallback((message: string | unknown) => {
    const msg = typeof message === "string" ? message : String(message);
    setErrorMessage(msg);
    setAppState("error");
  }, []);

  const handleConversionComplete = useCallback((folder: string) => {
    setOutputFolder(folder);
    setAppState("finished");
  }, []);

  const handleConvertAnother = useCallback(() => {
    setFileInfo(null);
    setOutputFolder("");
    setErrorMessage("");
    setAppState("upload");
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border/50">
        <div className="flex items-center gap-2.5">
          <div className="rounded-lg bg-primary p-1.5">
            <Layers className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="text-lg font-semibold tracking-tight">
            SlideDrop
          </span>
        </div>
        <ThemeToggle />
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-2xl mx-auto">
          {/* Title area */}
          {appState === "upload" && (
            <div className="text-center mb-10 animate-fade-in-up">
              <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
                Convert slides to images
              </h1>
              <p className="mt-3 text-muted-foreground text-base max-w-md mx-auto">
                Upload a PowerPoint or PDF file and export every slide as a
                high-quality PNG image.
              </p>
            </div>
          )}

          {/* State views */}
          {appState === "upload" && (
            <UploadZone
              onFileUploaded={handleFileUploaded}
              onError={handleError}
            />
          )}

          {appState === "processing" && fileInfo && (
            <ProcessingView
              jobId={fileInfo.jobId}
              customOutputFolder={fileInfo.customOutputFolder}
              onComplete={handleConversionComplete}
              onError={handleError}
            />
          )}

          {appState === "finished" && (
            <FinishedView
              outputFolder={outputFolder}
              onConvertAnother={handleConvertAnother}
            />
          )}

          {appState === "error" && (
            <div className="animate-fade-in-up w-full max-w-lg mx-auto">
              <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-8 text-center">
                <div className="rounded-full bg-destructive/10 p-3 w-fit mx-auto mb-4">
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
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  Something went wrong
                </h3>
                <p className="text-sm text-muted-foreground mb-6 whitespace-pre-wrap">
                  {errorMessage}
                </p>
                <button
                  onClick={handleConvertAnother}
                  className="text-sm font-medium text-primary hover:text-primary/80 transition-colors cursor-pointer"
                >
                  Try again
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="px-6 py-4 text-center border-t border-border/50">
        <p className="text-xs text-muted-foreground">
          SlideDrop — Slide-to-image converter. Files are processed locally.
        </p>
      </footer>
    </div>
  );
}
