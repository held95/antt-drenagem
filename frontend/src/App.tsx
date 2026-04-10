import { useCallback, useEffect, useState } from "react";
import { Header } from "./components/layout/Header";
import { Footer } from "./components/layout/Footer";
import { DropZone } from "./components/upload/DropZone";
import { FileList } from "./components/upload/FileList";
import { ProcessingStatus } from "./components/processing/ProcessingStatus";
import { ResultsPanel } from "./components/results/ResultsPanel";
import { useJobStatus } from "./hooks/useJobStatus";
import { uploadPdfs } from "./lib/api";
import type { AppState } from "./types";
import { Loader2 } from "lucide-react";

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [appState, setAppState] = useState<AppState>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { status: jobStatus } = useJobStatus(jobId);

  // G7 fix: move state transitions to useEffect instead of during render
  useEffect(() => {
    if (!jobStatus) return;
    if (jobStatus.status === "completed" && appState === "processing") {
      setAppState("completed");
    }
    if (jobStatus.status === "error" && appState === "processing") {
      setAppState("error");
    }
  }, [jobStatus, appState]);

  const handleFilesAdded = useCallback((newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
    setUploadError(null);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleClearAll = useCallback(() => {
    setFiles([]);
  }, []);

  const handleProcess = async () => {
    if (files.length === 0) return;
    setAppState("uploading");
    setUploadError(null);

    try {
      const response = await uploadPdfs(files);
      setJobId(response.job_id);
      setAppState("processing");
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Erro no upload");
      setAppState("idle");
    }
  };

  const handleReset = () => {
    setFiles([]);
    setJobId(null);
    setAppState("idle");
    setUploadError(null);
  };

  const isProcessing = appState === "uploading" || appState === "processing";

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-8">
        {/* Upload section */}
        {(appState === "idle" || appState === "uploading") && (
          <div className="space-y-4">
            <DropZone
              onFilesAdded={handleFilesAdded}
              disabled={isProcessing}
            />
            <FileList
              files={files}
              onRemove={handleRemoveFile}
              onClearAll={handleClearAll}
              disabled={isProcessing}
            />

            {uploadError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger">
                {uploadError}
              </div>
            )}

            {files.length > 0 && (
              <div className="flex justify-center">
                <button
                  onClick={handleProcess}
                  disabled={isProcessing}
                  className="flex items-center gap-2 rounded-lg bg-primary px-8 py-3 font-medium text-white shadow transition-colors hover:bg-primary-light disabled:opacity-50"
                >
                  {appState === "uploading" ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Enviando...
                    </>
                  ) : (
                    <>Processar {files.length} arquivo{files.length > 1 ? "s" : ""}</>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Processing status */}
        {(appState === "processing" || appState === "error") && jobStatus && (
          <div className="space-y-4">
            <ProcessingStatus jobStatus={jobStatus} />
            {appState === "error" && (
              <div className="flex justify-center">
                <button
                  onClick={handleReset}
                  className="rounded-lg border border-gray-300 bg-white px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Tentar novamente
                </button>
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {appState === "completed" && jobStatus && (
          <div className="space-y-4">
            <ProcessingStatus jobStatus={jobStatus} />
            <ResultsPanel jobStatus={jobStatus} onReset={handleReset} />
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
