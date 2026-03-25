"use client";

import { useEffect, useRef, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Loader2, Sparkles } from "lucide-react";
import { apiUrl } from "@/lib/api";

interface ProcessingViewProps {
    jobId: string;
    customOutputFolder?: string;
    extractText?: boolean;
    parallelism?: number;
    modelChoice?: "3b" | "7b";
    onComplete: (outputFolder: string, extractionFile?: string) => void;
    onError: (message: string) => void;
}

export function ProcessingView({
    jobId,
    customOutputFolder,
    extractText,
    parallelism,
    modelChoice,
    onComplete,
    onError,
}: ProcessingViewProps) {
    const [currentSlide, setCurrentSlide] = useState(0);
    const [totalSlides, setTotalSlides] = useState(0);
    const [hasStarted, setHasStarted] = useState(false);
    const [phase, setPhase] = useState<"converting" | "extracting">("converting");
    const [extractionCurrent, setExtractionCurrent] = useState(0);
    const [extractionTotal, setExtractionTotal] = useState(0);
    const [extractionActiveJobs, setExtractionActiveJobs] = useState(0);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);
    const startRequestedRef = useRef(false);

    useEffect(() => {
        if (startRequestedRef.current) return;
        startRequestedRef.current = true;

        // Start the conversion
        const startConversion = async () => {
            try {
                const res = await fetch(apiUrl("/convert"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        job_id: jobId,
                        output_folder: customOutputFolder || null,
                        extract_text: extractText || false,
                        parallelism: parallelism || 4,
                        model_choice: modelChoice || "3b",
                    }),
                });

                if (!res.ok) {
                    const data = await res.json();
                    const detail = typeof data.detail === "string"
                        ? data.detail
                        : JSON.stringify(data.detail);
                    throw new Error(detail || "Failed to start conversion");
                }

                setHasStarted(true);
            } catch (err) {
                onError(
                    err instanceof Error ? err.message : "Failed to start conversion."
                );
            }
        };

        startConversion();
    }, [jobId, customOutputFolder, extractText, parallelism, modelChoice, onError]);

    useEffect(() => {
        if (!hasStarted) return;

        const pollStatus = async () => {
            try {
                const res = await fetch(apiUrl(`/status?job_id=${jobId}`));
                if (!res.ok) return;

                const data = await res.json();
                setCurrentSlide(data.current_slide);
                setTotalSlides(data.total_slides);

                if (data.state === "extracting") {
                    setPhase("extracting");
                    setExtractionCurrent(data.extraction_current);
                    setExtractionTotal(data.extraction_total);
                    setExtractionActiveJobs(data.extraction_active_jobs);
                } else if (data.state === "done" || data.state === "complete") {
                    if (pollingRef.current) clearInterval(pollingRef.current);
                    onComplete(data.output_folder, data.extraction_file || undefined);
                } else if (data.state === "error") {
                    if (pollingRef.current) clearInterval(pollingRef.current);
                    onError(data.error || "Conversion failed.");
                }
            } catch {
                // Silently retry on network errors
            }
        };

        pollingRef.current = setInterval(pollStatus, 2000);
        pollStatus(); // Immediate first poll

        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        };
    }, [hasStarted, jobId, onComplete, onError]);

    const isExtracting = phase === "extracting";
    const selectedModelLabel = (modelChoice || "3b").toUpperCase();
    const progress = isExtracting
        ? (extractionTotal > 0
            ? Math.round((extractionCurrent / extractionTotal) * 100)
            : 0)
        : (totalSlides > 0
            ? Math.round((currentSlide / totalSlides) * 100)
            : 0);

    return (
        <div className="animate-fade-in-up w-full max-w-lg mx-auto">
            <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
                <div className="flex flex-col items-center text-center space-y-6">
                    <div className={`rounded-2xl p-4 ${isExtracting ? "bg-violet-500/10" : "bg-primary/10"}`}>
                        {isExtracting ? (
                            <Sparkles className="h-8 w-8 text-violet-500 animate-pulse" />
                        ) : (
                            <Loader2 className="h-8 w-8 text-primary animate-spin" />
                        )}
                    </div>

                    <div className="space-y-1.5">
                        <h3 className="text-lg font-semibold text-foreground">
                            {isExtracting ? "Extracting lecture text..." : "Converting slides..."}
                        </h3>
                        {isExtracting ? (
                            <div className="space-y-1">
                                <p className="text-sm text-muted-foreground">
                                    Slide{" "}
                                    <span className="font-mono font-medium text-foreground">
                                        {extractionCurrent}
                                    </span>{" "}
                                    of{" "}
                                    <span className="font-mono font-medium text-foreground">
                                        {extractionTotal}
                                    </span>{" "}
                                    processed
                                </p>
                                {extractionActiveJobs > 0 && (
                                    <p className="text-xs text-muted-foreground">
                                        Active jobs:{" "}
                                        <span className="font-mono font-medium text-violet-500">
                                            {extractionActiveJobs}
                                        </span>{" "}
                                        / {parallelism || 4}
                                    </p>
                                )}
                            </div>
                        ) : (
                            totalSlides > 0 && (
                                <p className="text-sm text-muted-foreground">
                                    Slide{" "}
                                    <span className="font-mono font-medium text-foreground">
                                        {currentSlide}
                                    </span>{" "}
                                    of{" "}
                                    <span className="font-mono font-medium text-foreground">
                                        {totalSlides}
                                    </span>
                                </p>
                            )
                        )}
                    </div>

                    <div className="w-full space-y-2">
                        <Progress
                            value={progress}
                            className="h-2.5 rounded-full"
                        />
                        <p className="text-xs text-muted-foreground text-right font-mono">
                            {progress}%
                        </p>
                    </div>

                    <p className="text-xs text-muted-foreground">
                        {isExtracting
                            ? `Processing slides with Qwen2.5-VL ${selectedModelLabel}`
                            : "Rendering at 300 DPI for maximum clarity"
                        }
                    </p>

                </div>
            </div>
        </div>
    );
}
