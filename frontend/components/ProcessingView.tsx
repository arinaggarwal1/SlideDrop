"use client";

import { useEffect, useRef, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Loader2 } from "lucide-react";

interface ProcessingViewProps {
    jobId: string;
    customOutputFolder?: string;
    onComplete: (outputFolder: string) => void;
    onError: (message: string) => void;
}

export function ProcessingView({
    jobId,
    customOutputFolder,
    onComplete,
    onError,
}: ProcessingViewProps) {
    const [currentSlide, setCurrentSlide] = useState(0);
    const [totalSlides, setTotalSlides] = useState(0);
    const [hasStarted, setHasStarted] = useState(false);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);
    const startRequestedRef = useRef(false);

    useEffect(() => {
        if (startRequestedRef.current) return;
        startRequestedRef.current = true;

        // Start the conversion
        const startConversion = async () => {
            try {
                const res = await fetch("http://localhost:8000/convert", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        job_id: jobId,
                        output_folder: customOutputFolder || null
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
    }, [jobId, customOutputFolder, onError]);

    useEffect(() => {
        if (!hasStarted) return;

        const pollStatus = async () => {
            try {
                const res = await fetch(
                    `http://localhost:8000/status?job_id=${jobId}`
                );
                if (!res.ok) return;

                const data = await res.json();
                setCurrentSlide(data.current_slide);
                setTotalSlides(data.total_slides);

                if (data.state === "done") {
                    if (pollingRef.current) clearInterval(pollingRef.current);
                    onComplete(data.output_folder);
                } else if (data.state === "error") {
                    if (pollingRef.current) clearInterval(pollingRef.current);
                    onError(data.error || "Conversion failed.");
                }
            } catch {
                // Silently retry on network errors
            }
        };

        pollingRef.current = setInterval(pollStatus, 500);
        pollStatus(); // Immediate first poll

        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        };
    }, [hasStarted, jobId, onComplete, onError]);

    const progress =
        totalSlides > 0 ? Math.round((currentSlide / totalSlides) * 100) : 0;

    return (
        <div className="animate-fade-in-up w-full max-w-lg mx-auto">
            <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
                <div className="flex flex-col items-center text-center space-y-6">
                    <div className="rounded-2xl bg-primary/10 p-4">
                        <Loader2 className="h-8 w-8 text-primary animate-spin" />
                    </div>

                    <div className="space-y-1.5">
                        <h3 className="text-lg font-semibold text-foreground">
                            Converting slides...
                        </h3>
                        {totalSlides > 0 && (
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
                        Rendering at 300 DPI for maximum clarity
                    </p>
                </div>
            </div>
        </div>
    );
}
