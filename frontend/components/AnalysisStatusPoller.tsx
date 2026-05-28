"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Evaluation } from "@/lib/types";

type AnalysisStatus = Evaluation["status"];

const activeStatuses = new Set<AnalysisStatus>(["queued", "running"]);

export function AnalysisStatusPoller({
  initialStatus,
  intervalMs = 8000
}: {
  initialStatus: AnalysisStatus;
  intervalMs?: number;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<AnalysisStatus>(initialStatus);
  const hasRefreshed = useRef(false);

  useEffect(() => {
    if (!activeStatuses.has(status)) return;

    const poll = window.setInterval(async () => {
      try {
        const response = await fetch("/api/analysis/latest", { cache: "no-store" });
        if (!response.ok) return;

        const evaluation = (await response.json()) as Evaluation | null;
        if (!evaluation?.status) return;

        setStatus(evaluation.status);
        if (!activeStatuses.has(evaluation.status) && !hasRefreshed.current) {
          hasRefreshed.current = true;
          router.refresh();
        }
      } catch {
        // Keep the current page stable; the next interval can try again.
      }
    }, intervalMs);

    return () => window.clearInterval(poll);
  }, [intervalMs, router, status]);

  return (
    <p className="muted analysis-progress-note">
      Analysis is {status}. You can keep this page open; it will update when the result is ready.
    </p>
  );
}
