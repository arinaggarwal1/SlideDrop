"use client";

import { useState } from "react";
import { FileText, FolderOpen, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";

interface FinishedViewProps {
    outputFolder: string;
    extractionFile?: string;
    onConvertAnother: () => void;
}

export function FinishedView({
    outputFolder,
    extractionFile,
    onConvertAnother,
}: FinishedViewProps) {
    const [isOpeningFolder, setIsOpeningFolder] = useState(false);
    const [openError, setOpenError] = useState("");
    const folderDisplay = outputFolder.split("/").slice(-2).join("/");

    const handleOpenFolder = async () => {
        setIsOpeningFolder(true);
        setOpenError("");

        try {
            const res = await fetch(apiUrl("/open-location"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path: outputFolder }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Failed to open the output folder.");
            }
        } catch (err) {
            setOpenError(err instanceof Error ? err.message : "Failed to open the output folder.");
        } finally {
            setIsOpeningFolder(false);
        }
    };

    return (
        <div className="animate-fade-in-up w-full max-w-lg mx-auto">
            <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
                <div className="flex flex-col items-center text-center space-y-6">
                    <div className="animate-bounce-in rounded-full bg-emerald-500/10 p-5">
                        <svg
                            className="h-12 w-12 text-emerald-500"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <circle
                                cx="12"
                                cy="12"
                                r="10"
                                className="opacity-20"
                                fill="currentColor"
                                stroke="none"
                            />
                            <path d="M8 12.5l2.5 2.5 5.5-5.5" className="animate-checkmark" />
                        </svg>
                    </div>

                    <div className="space-y-1.5">
                        <h3 className="text-xl font-semibold text-foreground">
                            Slides exported successfully!
                        </h3>
                        <p className="text-sm text-muted-foreground">
                            Your images are ready{extractionFile ? " with lecture notes" : ""}
                        </p>
                    </div>

                    <div className="w-full rounded-xl bg-muted/50 border border-border px-4 py-3">
                        <p className="text-xs text-muted-foreground mb-1">Saved to</p>
                        <p className="text-sm font-mono text-foreground truncate">
                            ~/{folderDisplay}
                        </p>
                    </div>

                    {extractionFile && (
                        <div className="w-full rounded-xl bg-violet-500/5 border border-violet-500/20 px-4 py-3">
                            <div className="flex items-center gap-2">
                                <FileText className="h-4 w-4 text-violet-500 shrink-0" />
                                <div className="min-w-0 text-left">
                                    <p className="text-xs text-muted-foreground mb-0.5">Lecture transcript</p>
                                    <p className="text-sm font-mono text-foreground truncate">
                                        lecture_extraction.txt
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {openError && (
                        <p className="w-full rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                            {openError}
                        </p>
                    )}

                    <div className="w-full space-y-3">
                        <Button
                            size="lg"
                            className="w-full rounded-xl h-12 text-base font-medium cursor-pointer shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all duration-300"
                            onClick={handleOpenFolder}
                            disabled={isOpeningFolder}
                        >
                            <FolderOpen className="h-4 w-4 mr-2" />
                            {isOpeningFolder ? "Opening Folder..." : "Open Folder"}
                        </Button>

                        <Button
                            variant="outline"
                            size="lg"
                            className="w-full rounded-xl h-12 text-base font-medium cursor-pointer transition-all duration-300"
                            onClick={onConvertAnother}
                        >
                            <RotateCcw className="h-4 w-4 mr-2" />
                            Convert Another File
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}
