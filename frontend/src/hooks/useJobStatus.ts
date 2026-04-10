import { useCallback, useEffect, useRef, useState } from "react";
import { getJobStatus } from "../lib/api";
import type { JobStatus } from "../types";

export function useJobStatus(jobId: string | null) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!jobId) {
      setStatus(null);
      setError(null);
      return;
    }

    const poll = async () => {
      try {
        const data = await getJobStatus(jobId);
        setStatus(data);

        if (data.status === "completed" || data.status === "error") {
          stopPolling();
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro desconhecido");
        stopPolling();
      }
    };

    // Poll immediately then every 1s
    poll();
    intervalRef.current = setInterval(poll, 1000);

    return stopPolling;
  }, [jobId, stopPolling]);

  return { status, error };
}
