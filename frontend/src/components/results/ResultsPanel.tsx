import { Download, RefreshCw } from "lucide-react";
import type { ProcessResponse } from "../../types";
import { useState } from "react";

interface ResultsPanelProps {
  result: ProcessResponse;
  onReset: () => void;
}

export function ResultsPanel({ result, onReset }: ResultsPanelProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = () => {
    if (!result.excel_base64) return;
    setDownloading(true);
    try {
      const byteChars = atob(result.excel_base64);
      const byteNumbers = new Uint8Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
      }
      const blob = new Blob([byteNumbers], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "drenagem_consolidado.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6">
      <div className="mb-4 text-center">
        <p className="text-lg font-medium text-gray-800">
          {result.successful_files} arquivo{result.successful_files > 1 ? "s" : ""} processado
          {result.successful_files > 1 ? "s" : ""} com sucesso
        </p>
        <p className="text-sm text-gray-500">
          O arquivo Excel está pronto para download
        </p>
      </div>

      <div className="flex items-center justify-center gap-4">
        <button
          onClick={handleDownload}
          disabled={downloading || !result.excel_base64}
          className="flex items-center gap-2 rounded-lg bg-success px-6 py-3 font-medium text-white shadow transition-colors hover:bg-green-600 disabled:opacity-50"
        >
          <Download className="h-5 w-5" />
          {downloading ? "Baixando..." : "Baixar Excel"}
        </button>
        <button
          onClick={onReset}
          className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-6 py-3 font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          <RefreshCw className="h-5 w-5" />
          Novo Lote
        </button>
      </div>
    </div>
  );
}
