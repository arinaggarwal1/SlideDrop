"use client";

import React, { useCallback, useState, useRef } from "react";
import { Upload, FileText, FileIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

interface UploadZoneProps {
    onFileUploaded: (data: {
        jobId: string;
        filename: string;
        fileType: string;
        pageCount: number;
        customOutputFolder?: string;
    }) => void;
    onError: (message: string) => void;
}

export function UploadZone({ onFileUploaded, onError }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadedFile, setUploadedFile] = useState<{
        jobId: string;
        filename: string;
        fileType: string;
        pageCount: number;
    } | null>(null);
    const [customFolder, setCustomFolder] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFile = useCallback(
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

                const res = await fetch("http://localhost:8000/upload", {
                    method: "POST",
                    body: formData,
                });

                if (!res.ok) {
                    const data = await res.json();
                    throw new Error(data.detail || "Upload failed");
                }

                const data = await res.json();
                setUploadedFile({
                    jobId: data.job_id,
                    filename: data.filename,
                    fileType: data.file_type,
                    pageCount: data.page_count,
                });
            } catch (err) {
                onError(
                    err instanceof Error ? err.message : "Failed to upload file."
                );
            } finally {
                setIsUploading(false);
            }
        },
        [onError]
    );

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        },
        [handleFile]
    );

    const handleClick = () => {
        fileInputRef.current?.click();
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            handleFile(files[0]);
        }
    };

    const handleConvert = () => {
        if (uploadedFile) {
            onFileUploaded({
                ...uploadedFile,
                customOutputFolder: customFolder.trim() || undefined,
            });
        }
    };

    const getFileIcon = () => {
        if (uploadedFile?.fileType === ".pdf") {
            return <FileText className="h-6 w-6 text-red-500" />;
        }
        return <FileIcon className="h-6 w-6 text-orange-500" />;
    };

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
              relative cursor-pointer rounded-2xl border-2 border-dashed
              p-16 text-center transition-all duration-300 ease-out
              ${isDragging
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
                                className={`
                  rounded-2xl p-4 transition-all duration-300
                  ${isDragging
                                        ? "bg-primary/10 text-primary scale-110"
                                        : "bg-muted text-muted-foreground"
                                    }
                `}
                            >
                                <Upload className="h-8 w-8" />
                            </div>

                            {isUploading ? (
                                <div className="space-y-2">
                                    <p className="text-lg font-medium animate-pulse-soft">
                                        Uploading...
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    <p className="text-lg font-medium text-foreground">
                                        Drop your PowerPoint or PDF here
                                    </p>
                                    <p className="text-sm text-muted-foreground">
                                        or click to browse files
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="mt-4 flex items-center justify-center gap-3 text-xs text-muted-foreground">
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
                            <div className="rounded-xl bg-muted p-3">
                                {getFileIcon()}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-foreground truncate">
                                    {uploadedFile.filename}
                                </p>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    {uploadedFile.pageCount}{" "}
                                    {uploadedFile.pageCount === 1 ? "slide" : "slides"} detected
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-2 text-left">
                            <label className="text-sm font-medium text-foreground">
                                Save to Folder (Optional)
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. /Users/name/Desktop"
                                value={customFolder}
                                onChange={(e) => setCustomFolder(e.target.value)}
                                className="flex h-10 w-full rounded-xl border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 transition-colors duration-200"
                            />
                            <p className="text-xs text-muted-foreground">
                                Leave blank to save automatically in your Downloads folder.
                            </p>
                        </div>
                        <Button
                            onClick={handleConvert}
                            size="lg"
                            className="w-full rounded-xl h-12 text-base font-medium cursor-pointer shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/30 transition-all duration-300"
                        >
                            Convert Slides
                        </Button>
                    </div>

                    <button
                        onClick={() => {
                            setUploadedFile(null);
                            if (fileInputRef.current) fileInputRef.current.value = "";
                        }}
                        className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    >
                        Choose a different file
                    </button>
                </div>
            )}
        </div>
    );
}
