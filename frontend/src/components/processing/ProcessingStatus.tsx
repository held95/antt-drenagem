import { AlertTriangle, CheckCircle, Loader2, XCircle } from "lucide-react";
import type { ProcessResponse } from "../../types";
import { cn } from "../../lib/cn";

interface ProcessingStatusProps {
  result: ProcessResponse | null;
  isProcessing: boolean;
}

export function ProcessingStatus({ result, isProcessing }: ProcessingStatusProps) {
  if (isProcessing) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="flex flex-col items-center gap-3 py-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary" />
          <p className="text-sm font-medium text-gray-700">
            Processando arquivos... Isso pode levar alguns segundos.
          </p>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const { total_files, successful_files, files } = result;
  const percent = total_files > 0 ? Math.round((successful_files / total_files) * 100) : 0;
  const isCompleted = successful_files > 0;
  const isError = successful_files === 0;

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
            {isCompleted ? (
              <CheckCircle className="h-4 w-4 text-success" />
            ) : (
              <XCircle className="h-4 w-4 text-danger" />
            )}
            {isCompleted ? "Concluído" : "Erro"}
          </span>
          <span className="text-sm text-gray-500">
            {successful_files}/{total_files} ({percent}%)
          </span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              isError ? "bg-danger" : "bg-success"
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-sm">
        <span className="flex items-center gap-1 text-success">
          <CheckCircle className="h-3.5 w-3.5" />
          {successful_files} sucesso
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
