import { Download, RefreshCw } from "lucide-react";
import type { JobStatus } from "../../types";
import { downloadExcel } from "../../lib/api";
import { useState } from "react";

interface ResultsPanelProps {
  jobStatus: JobStatus;
  onReset: () => void;
}

export function ResultsPanel({ jobStatus, onReset }: ResultsPanelProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await downloadExcel(jobStatus.job_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `drenagem_consolidado_${jobStatus.job_id.slice(0, 8)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Erro ao baixar o Excel. Tente novamente.");
    } finally {
      setDownloading(false);
    }
  };

  const successCount = jobStatus.files.filter(
    (f) => f.status === "success"
  ).length;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6">
      <div className="mb-4 text-center">
        <p className="text-lg font-medium text-gray-800">
          {successCount} PDF{successCount > 1 ? "s" : ""} processado
          {successCount > 1 ? "s" : ""} com sucesso
        </p>
        <p className="text-sm text-gray-500">
          O arquivo Excel está pronto para download
        </p>
      </div>

      <div className="flex items-center justify-center gap-4">
        <button
          onClick={handleDownload}
          disabled={downloading || !jobStatus.download_ready}
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
