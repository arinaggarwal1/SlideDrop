"use client";

import { FolderOpen, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FinishedViewProps {
    outputFolder: string;
    onConvertAnother: () => void;
}

export function FinishedView({
    outputFolder,
    onConvertAnother,
}: FinishedViewProps) {
    // Extract just the folder name for display
    const folderDisplay = outputFolder.split("/").slice(-2).join("/");

    return (
        <div className="animate-fade-in-up w-full max-w-lg mx-auto">
            <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
                <div className="flex flex-col items-center text-center space-y-6">
                    {/* Animated success checkmark */}
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
                            Your images are ready
                        </p>
                    </div>

                    {/* Output folder path */}
                    <div className="w-full rounded-xl bg-muted/50 border border-border px-4 py-3">
                        <p className="text-xs text-muted-foreground mb-1">Saved to</p>
                        <p className="text-sm font-mono text-foreground truncate">
                            ~/{folderDisplay}
                        </p>
                    </div>

                    {/* Action buttons */}
                    <div className="w-full space-y-3">
                        <Button
                            size="lg"
                            className="w-full rounded-xl h-12 text-base font-medium cursor-pointer shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all duration-300"
                            onClick={() => {
                                // Open folder in Finder - the backend doesn't have this endpoint
                                // but the folder path is shown for user reference
                                window.open(`file://${outputFolder}`, "_blank");
                            }}
                        >
                            <FolderOpen className="h-4 w-4 mr-2" />
                            Open Folder
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
