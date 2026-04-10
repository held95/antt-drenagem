import { AlertTriangle, CheckCircle, Loader2, XCircle } from "lucide-react";
import type { JobStatus } from "../../types";
import { cn } from "../../lib/cn";

interface ProcessingStatusProps {
  jobStatus: JobStatus;
}

export function ProcessingStatus({ jobStatus }: ProcessingStatusProps) {
  const { status, total_files, processed_files, files } = jobStatus;
  const percent =
    total_files > 0 ? Math.round((processed_files / total_files) * 100) : 0;

  const isProcessing = status === "processing";
  const isCompleted = status === "completed";
  const isError = status === "error";

  const successCount = files.filter((f) => f.status === "success").length;
  const errorCount = files.filter((f) => f.status === "error").length;
  const warningCount = files.filter(
    (f) => f.warnings && f.warnings.length > 0
  ).length;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6">
      {/* Progress bar */}
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
            {isProcessing && (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            )}
            {isCompleted && (
              <CheckCircle className="h-4 w-4 text-success" />
            )}
            {isError && <XCircle className="h-4 w-4 text-danger" />}
            {isProcessing
              ? "Processando..."
              : isCompleted
                ? "Concluído"
                : "Erro"}
          </span>
          <span className="text-sm text-gray-500">
            {processed_files}/{total_files} ({percent}%)
          </span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              isError ? "bg-danger" : isCompleted ? "bg-success" : "bg-primary"
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-sm">
        <span className="flex items-center gap-1 text-success">
          <CheckCircle className="h-3.5 w-3.5" />
          {successCount} sucesso
        </span>
        {warningCount > 0 && (
          <span className="flex items-center gap-1 text-warning">
            <AlertTriangle className="h-3.5 w-3.5" />
            {warningCount} avisos
          </span>
        )}
        {errorCount > 0 && (
          <span className="flex items-center gap-1 text-danger">
            <XCircle className="h-3.5 w-3.5" />
            {errorCount} erros
          </span>
        )}
      </div>

      {/* File-level warnings/errors */}
      {files.some((f) => f.warnings.length > 0 || f.error) && (
        <div className="mt-4 max-h-40 space-y-1 overflow-y-auto border-t border-gray-100 pt-3">
          {files
            .filter((f) => f.warnings.length > 0 || f.error)
            .map((f) => (
              <div key={f.filename} className="text-xs text-gray-600">
                <span className="font-medium">{f.filename}:</span>{" "}
                {f.error ? (
                  <span className="text-danger">{f.error}</span>
                ) : (
                  f.warnings.join("; ")
                )}
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
