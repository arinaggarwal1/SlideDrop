"use client";

import React, { useCallback, useRef, useState } from "react";
import { FileIcon, FileText, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";

interface UploadZoneProps {
  onFileUploaded: (data: {
    jobId: string;
    filename: string;
    fileType: string;
    pageCount: number;
    customOutputFolder?: string;
    extractText?: boolean;
    parallelism?: number;
    modelChoice?: "3b" | "7b";
  }) => void;
  onError: (message: string) => void;
}

interface UploadedFileState {
  jobId: string;
  filename: string;
  fileType: string;
  pageCount: number;
}

export function UploadZone({ onFileUploaded, onError }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFileState | null>(null);
  const [customFolder, setCustomFolder] = useState("");
  const [extractText, setExtractText] = useState(false);
  const [parallelism, setParallelism] = useState(4);
  const [modelChoice, setModelChoice] = useState<"3b" | "7b">("3b");
  const [pageRange, setPageRange] = useState("");
  const [isExtractingRange, setIsExtractingRange] = useState(false);
  const [isExtractingText, setIsExtractingText] = useState(false);
  const [isBrowsingFolder, setIsBrowsingFolder] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const storeUploadedFile = useCallback((data: {
    job_id: string;
    filename: string;
    file_type: string;
    page_count: number;
  }) => {
    setUploadedFile({
      jobId: data.job_id,
      filename: data.filename,
      fileType: data.file_type,
      pageCount: data.page_count,
    });
    setPageRange(`1-${data.page_count}`);
  }, []);

  const uploadSingleFile = useCallback(
    async (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext !== "pptx" && ext !== "pdf") {
        onError("Only PDF and PowerPoint (.pptx) files are supported.");
        return;
      }

      setIsUploading(true);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(apiUrl("/upload"), {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || "Upload failed");
        }

        storeUploadedFile(await res.json());
      } catch (err) {
        onError(err instanceof Error ? err.message : "Failed to upload file.");
      } finally {
        setIsUploading(false);
      }
    },
    [onError, storeUploadedFile]
  );

  const handleFiles = useCallback(
    async (incomingFiles: FileList | File[]) => {
      const files = Array.from(incomingFiles);
      if (files.length === 0) {
        return;
      }
      if (files.length > 1) {
        onError("The converter takes one file at a time. Use the Merge PDFs tool on the home screen for multi-PDF workflows.");
        return;
      }

      await uploadSingleFile(files[0]);
    },
    [onError, uploadSingleFile]
  );

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      void handleFiles(event.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      void handleFiles(files);
    }
  };

  const handleConvert = () => {
    if (!uploadedFile) {
      return;
    }

    onFileUploaded({
      jobId: uploadedFile.jobId,
      filename: uploadedFile.filename,
      fileType: uploadedFile.fileType,
      pageCount: uploadedFile.pageCount,
      customOutputFolder: customFolder.trim() || undefined,
      extractText,
      parallelism,
      modelChoice,
    });
  };

  const handleBrowseFolder = useCallback(async () => {
    setIsBrowsingFolder(true);
    try {
      const res = await fetch(apiUrl("/dialog/select-folder"), {
        method: "POST",
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to open the folder picker.");
      }

      const data = await res.json();
      if (data.path) {
        setCustomFolder(data.path);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to open the folder picker.");
    } finally {
      setIsBrowsingFolder(false);
    }
  }, [onError]);

  const handleExtractRange = useCallback(async () => {
    if (!uploadedFile) {
      return;
    }
    if (!pageRange.trim()) {
      onError("Please enter a page range like 20-40.");
      return;
    }

    setIsExtractingRange(true);
    try {
      const res = await fetch(apiUrl("/extract-pdf-range"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: uploadedFile.jobId,
          page_range: pageRange.trim(),
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to extract page range.");
      }

      const blob = await res.blob();
      const contentDisposition = res.headers.get("content-disposition") || "";
      const filenameMatch = /filename=\"?([^\"]+)\"?/.exec(contentDisposition);
      const downloadName = filenameMatch?.[1] || "extracted_pages.pdf";

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = downloadName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(
        err instanceof Error
          ? err.message
          : "Failed to extract and download the selected page range."
      );
    } finally {
      setIsExtractingRange(false);
    }
  }, [onError, pageRange, uploadedFile]);

  const handleExtractText = useCallback(async () => {
    if (!uploadedFile) {
      return;
    }

    setIsExtractingText(true);
    try {
      const res = await fetch(apiUrl("/extract-pdf-text"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: uploadedFile.jobId,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to extract PDF text.");
      }

      const blob = await res.blob();
      const contentDisposition = res.headers.get("content-disposition") || "";
      const filenameMatch = /filename=\"?([^\"]+)\"?/.exec(contentDisposition);
      const downloadName = filenameMatch?.[1] || "pdf_text.txt";

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = downloadName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      onError(
        err instanceof Error
          ? err.message
          : "Failed to extract and download text from the PDF."
      );
    } finally {
      setIsExtractingText(false);
    }
  }, [onError, uploadedFile]);

  const resetUpload = () => {
    setUploadedFile(null);
    setCustomFolder("");
    setPageRange("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const getFileIcon = () => {
    if (uploadedFile?.fileType === ".pdf") {
      return <FileText className="h-6 w-6 text-red-500" />;
    }
    return <FileIcon className="h-6 w-6 text-orange-500" />;
  };

  const pageLabel = uploadedFile?.fileType === ".pptx" ? "slides" : "pages";

  return (
    <div className="animate-fade-in-up w-full max-w-lg mx-auto">
      {!uploadedFile ? (
        <>
          <div
            onClick={handleClick}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              relative cursor-pointer rounded-2xl border-2 border-dashed p-16 text-center transition-all duration-300 ease-out
              ${
                isDragging
                  ? "border-primary bg-primary/5 scale-[1.02] shadow-lg shadow-primary/10"
                  : "border-border hover:border-primary/50 hover:bg-accent/50"
              }
              ${isUploading ? "pointer-events-none opacity-60" : ""}
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pptx,.pdf"
              onChange={handleInputChange}
              className="hidden"
            />

            <div className="flex flex-col items-center gap-4">
              <div
                className={`rounded-2xl p-4 transition-all duration-300 ${
                  isDragging ? "bg-primary/10 text-primary scale-110" : "bg-muted text-muted-foreground"
                }`}
              >
                <Upload className="h-8 w-8" />
              </div>

              {isUploading ? (
                <div className="space-y-2">
                  <p className="text-lg font-medium animate-pulse-soft">Uploading...</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-lg font-medium text-foreground">
                    Drop in one PowerPoint or PDF
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Click to browse, then we&apos;ll convert each slide into a crisp PNG set.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 flex items-center justify-center gap-3 text-xs text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5">
              <FileIcon className="h-3 w-3 text-orange-500" />
              .pptx
            </span>
            <span className="flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5">
              <FileText className="h-3 w-3 text-red-500" />
              .pdf
            </span>
          </div>
        </>
      ) : (
        <div className="animate-scale-in space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center gap-4">
              <div className="rounded-xl bg-muted p-3">{getFileIcon()}</div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-foreground truncate">{uploadedFile.filename}</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {uploadedFile.pageCount} {uploadedFile.pageCount === 1 ? pageLabel?.slice(0, -1) : pageLabel} detected
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="space-y-2 text-left">
              <label className="text-sm font-medium text-foreground">Save to Folder (Optional)</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. /Users/name/Desktop"
                  value={customFolder}
                  onChange={(event) => setCustomFolder(event.target.value)}
                  className="flex h-10 w-full rounded-xl border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-colors duration-200"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleBrowseFolder}
                  disabled={isBrowsingFolder}
                  className="rounded-xl shrink-0 cursor-pointer"
                >
                  {isBrowsingFolder ? "Opening..." : "Browse"}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Leave blank to save automatically in your Downloads folder.
              </p>
            </div>

            <div className="rounded-xl border border-border bg-card/50 p-4 space-y-3">
              <div className="text-left">
                <label className="text-sm font-medium text-foreground">Extract Sub-PDF by Page Range</label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Example: 20-40 (inclusive). Download a new PDF with only those pages.
                </p>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. 20-40"
                  value={pageRange}
                  onChange={(event) => setPageRange(event.target.value)}
                  className="flex h-10 w-full rounded-xl border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-colors duration-200"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleExtractRange}
                  disabled={isExtractingRange}
                  className="rounded-xl shrink-0 cursor-pointer"
                >
                  {isExtractingRange ? "Preparing..." : "Download"}
                </Button>
              </div>
            </div>

            {uploadedFile.fileType === ".pdf" && (
              <div className="rounded-xl border border-border bg-card/50 p-4 space-y-3">
                <div className="text-left">
                  <label className="text-sm font-medium text-foreground">Extract Embedded PDF Text</label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Downloads a plain text file using the text already embedded in the PDF.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleExtractText}
                  disabled={isExtractingText}
                  className="w-full rounded-xl cursor-pointer"
                >
                  {isExtractingText ? "Preparing Text..." : "Download Text File"}
                </Button>
              </div>
            )}

            <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <div className="flex items-start gap-3">
                <input
                  id="extract-text"
                  type="checkbox"
                  checked={extractText}
                  onChange={(event) => setExtractText(event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
                <div className="flex-1 text-left">
                  <label htmlFor="extract-text" className="text-sm font-medium text-foreground cursor-pointer">
                    Extract lecture notes with Ollama
                  </label>
                  <p className="text-xs text-muted-foreground mt-1">
                    Runs a local vision model on each rendered slide and writes a `lecture_extraction.txt` file.
                  </p>
                </div>
              </div>

              {extractText && (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2 text-left">
                    <label className="text-sm font-medium text-foreground">Parallelism</label>
                    <input
                      type="number"
                      min={1}
                      max={8}
                      value={parallelism}
                      onChange={(event) => setParallelism(Number(event.target.value) || 1)}
                      className="flex h-10 w-full rounded-xl border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-colors duration-200"
                    />
                  </div>
                  <div className="space-y-2 text-left">
                    <label className="text-sm font-medium text-foreground">Model</label>
                    <select
                      value={modelChoice}
                      onChange={(event) => setModelChoice(event.target.value as "3b" | "7b")}
                      className="flex h-10 w-full rounded-xl border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-colors duration-200"
                    >
                      <option value="3b">Llama 3.2 Vision 3B</option>
                      <option value="7b">Llama 3.2 Vision 7B</option>
                    </select>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-3">
              <Button
                variant="outline"
                size="lg"
                className="flex-1 rounded-xl h-12 cursor-pointer"
                onClick={resetUpload}
              >
                Choose Another File
              </Button>
              <Button
                size="lg"
                className="flex-1 rounded-xl h-12 cursor-pointer"
                onClick={handleConvert}
              >
                Convert Slides
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
