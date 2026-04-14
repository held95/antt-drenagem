import { useCallback, useState } from "react";
import { Header } from "./components/layout/Header";
import { Footer } from "./components/layout/Footer";
import { DropZone } from "./components/upload/DropZone";
import { FileList } from "./components/upload/FileList";
import { ProcessingStatus } from "./components/processing/ProcessingStatus";
import { ResultsPanel } from "./components/results/ResultsPanel";
import { processFiles } from "./lib/api";
import type { AppState, ProcessResponse } from "./types";

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [appState, setAppState] = useState<AppState>("idle");
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFilesAdded = useCallback((newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
    setErrorMsg(null);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleClearAll = useCallback(() => {
    setFiles([]);
  }, []);

  const handleProcess = async () => {
    if (files.length === 0) return;
    setAppState("processing");
    setErrorMsg(null);
    setResult(null);

    try {
      const response = await processFiles(files);
      setResult(response);
      setAppState(response.successful_files > 0 ? "completed" : "error");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Erro no processamento");
      setAppState("error");
    }
  };

  const handleReset = () => {
    setFiles([]);
    setResult(null);
    setAppState("idle");
    setErrorMsg(null);
  };

  const isProcessing = appState === "processing";

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main
        className={
          appState === "completed"
            ? "mx-auto w-full max-w-full flex-1 px-4 py-8"
            : "mx-auto w-full max-w-3xl flex-1 px-6 py-8"
        }
      >
        {/* Upload section */}
        {appState === "idle" && (
          <div className="space-y-4">
            <DropZone
              onFilesAdded={handleFilesAdded}
              disabled={false}
            />
            <FileList
              files={files}
              onRemove={handleRemoveFile}
              onClearAll={handleClearAll}
              disabled={false}
            />

            {errorMsg && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger">
                {errorMsg}
              </div>
            )}

            {files.length > 0 && (
              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={handleProcess}
                  className="flex items-center gap-2 rounded-lg bg-primary px-8 py-3 font-medium text-white shadow transition-colors hover:bg-primary-light disabled:opacity-50"
                >
                  Processar {files.length} arquivo{files.length > 1 ? "s" : ""}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Processing spinner */}
        {isProcessing && (
          <ProcessingStatus result={null} isProcessing={true} />
        )}

        {/* Error state */}
        {appState === "error" && (
          <div className="space-y-4">
            {result && <ProcessingStatus result={result} isProcessing={false} />}
            {errorMsg && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-danger">
                {errorMsg}
              </div>
            )}
            <div className="flex justify-center">
              <button
                type="button"
                onClick={handleReset}
                className="rounded-lg border border-gray-300 bg-white px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Tentar novamente
              </button>
            </div>
          </div>
        )}

        {/* Results */}
        {appState === "completed" && result && (
          <div className="space-y-4">
            <ProcessingStatus result={result} isProcessing={false} />
            <ResultsPanel result={result} onReset={handleReset} />
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
