"use client";

import { useCallback, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowUpDown,
  CheckCircle2,
  ExternalLink,
  FileText,
  FolderOpen,
  GripVertical,
  Plus,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";

interface MergePdfWorkspaceProps {
  onBack: () => void;
}

interface MergePdfFile {
  path: string;
  filename: string;
  pageCount: number;
  pageRange: string;
}

interface MergeSuccess {
  outputPath: string;
  outputFolder: string;
  filename: string;
  pageCount: number;
  sourceCount: number;
}

interface RangeParseResult {
  count: number;
  error: string | null;
}

function defaultRange(pageCount: number): string {
  return pageCount <= 1 ? "1" : `1-${pageCount}`;
}

function parsePageRange(pageRange: string, totalPages: number): RangeParseResult {
  const normalized = pageRange.trim().toLowerCase().replace(/\s+/g, "");
  if (!normalized || normalized === "all") {
    return { count: totalPages, error: null };
  }

  let count = 0;
  for (const part of normalized.split(",")) {
    if (!part) {
      return { count: 0, error: "Use formats like 1-3,5,8-10." };
    }

    const match = part.match(/^(\d+)(?:-(\d+))?$/);
    if (!match) {
      return { count: 0, error: "Use formats like 1-3,5,8-10." };
    }

    const start = Number(match[1]);
    const end = Number(match[2] || match[1]);
    if (start < 1 || end < 1) {
      return { count: 0, error: "Pages start at 1." };
    }
    if (start > end) {
      return { count: 0, error: "Each range needs a valid start and end." };
    }
    if (end > totalPages) {
      return { count: 0, error: `This PDF only has ${totalPages} pages.` };
    }

    count += end - start + 1;
  }

  return { count, error: null };
}

function buildDefaultOutputName(filename: string): string {
  const stem = filename.replace(/\.pdf$/i, "");
  return `${stem}-merged.pdf`;
}

export function MergePdfWorkspace({ onBack }: MergePdfWorkspaceProps) {
  const [files, setFiles] = useState<MergePdfFile[]>([]);
  const [outputFolder, setOutputFolder] = useState("");
  const [outputName, setOutputName] = useState("");
  const [draggedPath, setDraggedPath] = useState<string | null>(null);
  const [isSelectingFiles, setIsSelectingFiles] = useState(false);
  const [isBrowsingFolder, setIsBrowsingFolder] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [isOpeningPath, setIsOpeningPath] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<MergeSuccess | null>(null);

  const fileSummaries = useMemo(
    () =>
      files.map((file) => ({
        ...file,
        parsed: parsePageRange(file.pageRange, file.pageCount),
      })),
    [files]
  );

  const totalSelectedPages = fileSummaries.reduce(
    (sum, file) => sum + (file.parsed.error ? 0 : file.parsed.count),
    0
  );
  const hasInvalidRanges = fileSummaries.some((file) => Boolean(file.parsed.error));

  const inspectPaths = useCallback(async (paths: string[]) => {
    const res = await fetch(apiUrl("/pdfs/inspect"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths }),
    });

    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || "Failed to inspect the selected PDFs.");
    }

    const data = await res.json();
    const nextFiles = (data.files || []).map(
      (file: { path: string; filename: string; page_count: number }) => ({
        path: file.path,
        filename: file.filename,
        pageCount: file.page_count,
        pageRange: defaultRange(file.page_count),
      })
    ) as MergePdfFile[];

    setFiles((current) => {
      const existing = new Map(current.map((file) => [file.path, file]));
      for (const file of nextFiles) {
        if (!existing.has(file.path)) {
          existing.set(file.path, file);
        }
      }
      return Array.from(existing.values());
    });

    setOutputName((current) => current || buildDefaultOutputName(nextFiles[0]?.filename || "merged"));
    setError("");
    setSuccess(null);
  }, []);

  const handleAddPdfs = useCallback(async () => {
    setIsSelectingFiles(true);
    try {
      const res = await fetch(apiUrl("/dialog/select-pdfs"), {
        method: "POST",
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to open the PDF picker.");
      }

      const data = await res.json();
      const paths = (data.paths || []) as string[];
      if (paths.length === 0) {
        return;
      }

      await inspectPaths(paths);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add PDFs.");
    } finally {
      setIsSelectingFiles(false);
    }
  }, [inspectPaths]);

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
        setOutputFolder(data.path);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to choose a save folder.");
    } finally {
      setIsBrowsingFolder(false);
    }
  }, []);

  const handleOpenPath = useCallback(async (path: string) => {
    setIsOpeningPath(true);
    try {
      const res = await fetch(apiUrl("/open-location"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to open that location.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open that location.");
    } finally {
      setIsOpeningPath(false);
    }
  }, []);

  const handleRemoveFile = useCallback((path: string) => {
    setFiles((current) => current.filter((file) => file.path !== path));
  }, []);

  const handleUpdateRange = useCallback((path: string, pageRange: string) => {
    setFiles((current) =>
      current.map((file) => (file.path === path ? { ...file, pageRange } : file))
    );
  }, []);

  const moveFile = useCallback((fromPath: string, toPath: string) => {
    setFiles((current) => {
      const fromIndex = current.findIndex((file) => file.path === fromPath);
      const toIndex = current.findIndex((file) => file.path === toPath);
      if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) {
        return current;
      }

      const next = [...current];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  }, []);

  const handleMerge = useCallback(async () => {
    if (files.length === 0) {
      setError("Add at least one PDF to start building your merged file.");
      return;
    }
    if (hasInvalidRanges) {
      setError("Fix the highlighted page selections before merging.");
      return;
    }

    setIsMerging(true);
    setError("");

    try {
      const res = await fetch(apiUrl("/merge-pdfs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          files: files.map((file) => ({
            path: file.path,
            page_range: file.pageRange,
          })),
          output_folder: outputFolder.trim() || undefined,
          output_name: outputName.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to merge PDFs.");
      }

      const data = await res.json();
      setSuccess({
        outputPath: data.output_path,
        outputFolder: data.output_folder,
        filename: data.filename,
        pageCount: data.page_count,
        sourceCount: data.source_count,
      });
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to merge PDFs.");
    } finally {
      setIsMerging(false);
    }
  }, [files, hasInvalidRanges, outputFolder, outputName]);

  const handleReset = useCallback(() => {
    setFiles([]);
    setOutputFolder("");
    setOutputName("");
    setSuccess(null);
    setError("");
  }, []);

  if (success) {
    return (
      <div className="animate-fade-in-up mx-auto w-full max-w-2xl">
        <div className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] p-8 shadow-sm dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
          <div className="mb-8 flex flex-col items-center text-center">
            <div className="mb-4 rounded-full bg-muted p-3 text-primary">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              Your merged PDF is ready
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
              {success.sourceCount} source {success.sourceCount === 1 ? "document" : "documents"}, {success.pageCount} total {success.pageCount === 1 ? "page" : "pages"}.
            </p>
          </div>

          <div className="rounded-xl border border-border bg-muted/40 p-4">
            <p className="text-xs font-medium text-muted-foreground">
              Saved File
            </p>
            <p className="mt-3 break-all font-mono text-sm text-foreground">
              {success.outputPath}
            </p>
          </div>

          {error && (
            <p className="mt-4 rounded-2xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {error}
            </p>
          )}

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <Button
              size="lg"
              className="h-12 rounded-2xl cursor-pointer"
              onClick={() => handleOpenPath(success.outputPath)}
              disabled={isOpeningPath}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              {isOpeningPath ? "Opening..." : "Open PDF"}
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="h-12 rounded-2xl cursor-pointer"
              onClick={() => handleOpenPath(success.outputFolder)}
              disabled={isOpeningPath}
            >
              <FolderOpen className="mr-2 h-4 w-4" />
              Show in Folder
            </Button>
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Button
              variant="outline"
              size="lg"
              className="h-12 rounded-2xl cursor-pointer"
              onClick={handleReset}
            >
              Merge More PDFs
            </Button>
            <Button
              variant="ghost"
              size="lg"
              className="h-12 rounded-2xl cursor-pointer"
              onClick={onBack}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Tools
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in-up w-full">
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <button
            type="button"
            onClick={onBack}
            className="mb-4 inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to tools
          </button>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            Merge PDFs
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
            Add PDFs, drag them into order, keep only the pages you want, and save the final file wherever you like.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] px-3 py-2 text-sm text-muted-foreground dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.96),rgba(24,28,40,0.92))]">
          <ArrowUpDown className="h-4 w-4 text-primary" />
          Drag cards to reorder before merging
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.9fr)]">
        <section className="space-y-5">
          <div className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.95))] p-5 shadow-sm dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-foreground">
                  Add PDFs
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                  Use your system file picker to grab a full set of files at once, then fine-tune exactly which pages make it into the final document.
                </p>
              </div>
              <Button
                className="h-10 rounded-xl cursor-pointer px-4"
                onClick={handleAddPdfs}
                disabled={isSelectingFiles}
              >
                <Plus className="mr-2 h-4 w-4" />
                {isSelectingFiles ? "Opening Picker..." : files.length === 0 ? "Choose PDFs" : "Add More PDFs"}
              </Button>
            </div>
          </div>

          {files.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] p-10 text-center dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.96),rgba(24,28,40,0.92))]">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-primary">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-foreground">
                Your merge canvas is empty
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                Start with a few PDFs, then we&apos;ll let you trim pages, reorder the stack, and export one polished document.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {fileSummaries.map((file, index) => (
                <article
                  key={file.path}
                  draggable
                  onDragStart={() => setDraggedPath(file.path)}
                  onDragEnd={() => setDraggedPath(null)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => {
                    if (draggedPath) {
                      moveFile(draggedPath, file.path);
                    }
                    setDraggedPath(null);
                  }}
                  className={`rounded-2xl border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(249,250,252,0.95))] p-5 shadow-sm transition-all duration-200 dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))] ${
                    draggedPath === file.path
                      ? "border-primary/60"
                      : "border-border/70 hover:border-primary/35"
                  }`}
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex min-w-0 gap-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted text-primary">
                        <span className="text-sm font-semibold">{index + 1}</span>
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-muted-foreground">
                          <GripVertical className="h-4 w-4" />
                          <span className="text-xs font-medium">
                            Drag to reorder
                          </span>
                        </div>
                        <h3 className="mt-2 truncate text-lg font-semibold text-foreground">
                          {file.filename}
                        </h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {file.pageCount} total {file.pageCount === 1 ? "page" : "pages"}
                        </p>
                      </div>
                    </div>

                    <Button
                      type="button"
                      variant="ghost"
                      className="h-10 rounded-xl px-3 text-muted-foreground hover:text-destructive cursor-pointer"
                      onClick={() => handleRemoveFile(file.path)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Remove
                    </Button>
                  </div>

                  <div className="mt-5 rounded-xl border border-border bg-muted/30 p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
                      <div className="flex-1">
                        <label className="text-sm font-medium text-foreground">
                          Pages to include
                        </label>
                        <input
                          type="text"
                          value={file.pageRange}
                          onChange={(event) => handleUpdateRange(file.path, event.target.value)}
                          placeholder="all or 1-3,5,8-10"
                          className={`mt-2 flex h-11 w-full rounded-2xl border bg-background/90 px-4 py-2 text-sm ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                            file.parsed.error ? "border-destructive/40" : "border-input"
                          }`}
                        />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          className="h-10 rounded-xl cursor-pointer"
                          onClick={() => handleUpdateRange(file.path, "all")}
                        >
                          All Pages
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-10 rounded-xl cursor-pointer"
                          onClick={() => handleUpdateRange(file.path, "1")}
                        >
                          First Page
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="h-10 rounded-xl cursor-pointer"
                          onClick={() => handleUpdateRange(file.path, defaultRange(file.pageCount))}
                        >
                          Reset
                        </Button>
                      </div>
                    </div>

                    <p className={`mt-3 text-sm ${file.parsed.error ? "text-destructive" : "text-muted-foreground"}`}>
                      {file.parsed.error
                        ? file.parsed.error
                        : `${file.parsed.count} ${file.parsed.count === 1 ? "page" : "pages"} selected from this PDF.`}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <aside className="xl:sticky xl:top-8 xl:self-start">
          <div className="rounded-2xl border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.96))] p-6 shadow-sm dark:bg-[linear-gradient(180deg,rgba(29,33,46,0.98),rgba(24,28,40,0.94))]">
            <div>
              <h2 className="text-xl font-semibold text-foreground">
                Save merged PDF
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Review the file count, choose a name, and pick a folder.
              </p>
            </div>

            <div className="mt-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-border bg-muted/35 p-4">
                  <p className="text-xs font-medium text-muted-foreground">
                    PDFs
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-foreground">{files.length}</p>
                </div>
                <div className="rounded-xl border border-border bg-muted/35 p-4">
                  <p className="text-xs font-medium text-muted-foreground">
                    Selected Pages
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-foreground">{totalSelectedPages}</p>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Output filename</label>
                <input
                  type="text"
                  value={outputName}
                  onChange={(event) => setOutputName(event.target.value)}
                  placeholder="merged_document.pdf"
                  className="flex h-11 w-full rounded-2xl border border-input bg-background/90 px-4 py-2 text-sm ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Save location</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={outputFolder}
                    onChange={(event) => setOutputFolder(event.target.value)}
                    placeholder="Defaults to your Downloads folder"
                    className="flex h-11 w-full rounded-2xl border border-input bg-background/90 px-4 py-2 text-sm ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 rounded-2xl px-4 cursor-pointer"
                    onClick={handleBrowseFolder}
                    disabled={isBrowsingFolder}
                  >
                    {isBrowsingFolder ? "Opening..." : "Browse"}
                  </Button>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-muted/25 px-4 py-3 text-sm text-muted-foreground">
                If you leave the folder blank, the merged PDF will be saved in Downloads. The file name is adjusted automatically if one already exists.
              </div>

              {error && (
                <p className="rounded-2xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                  {error}
                </p>
              )}

              <Button
                size="lg"
                className="h-12 w-full rounded-2xl cursor-pointer text-base shadow-lg shadow-primary/20"
                onClick={handleMerge}
                disabled={isMerging || files.length === 0 || hasInvalidRanges}
              >
                <FileText className="mr-2 h-4 w-4" />
                {isMerging ? "Merging PDFs..." : "Merge PDFs"}
              </Button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
