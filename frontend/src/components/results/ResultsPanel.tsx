import { useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import type { ColumnDef, DrainageRecordData, ProcessResponse } from "../../types";
import { generateExcelCustom } from "../../lib/api";
import { ExcelPreviewTable } from "./ExcelPreviewTable";
import { UnmappedFieldsPanel } from "./UnmappedFieldsPanel";

interface ResultsPanelProps {
  result: ProcessResponse;
  onReset: () => void;
}

// Default column definitions — must match excel_generator.py COLUMNS order
const DEFAULT_COLUMNS: ColumnDef[] = [
  { field: "estaca_inicio",    label: "Estaca",               group: "Localização do Início" },
  { field: "km_inicial",       label: "Km",                   group: "Localização do Início" },
  { field: "latitude_inicio",  label: "Início Coordenada X",  group: "Localização do Início" },
  { field: "longitude_inicio", label: "Início Coordenada Y",  group: "Localização do Início" },
  { field: "estaca_fim",       label: "Estaca",               group: "Localização do Fim" },
  { field: "km_final",         label: "Km",                   group: "Localização do Fim" },
  { field: "latitude_fim",     label: "Fim Coordenada X",     group: "Localização do Fim" },
  { field: "longitude_fim",    label: "Fim Coordenada Y",     group: "Localização do Fim" },
  { field: "altura",           label: "Altura",               group: "Dimensões" },
  { field: "extensao",         label: "Extensão",             group: "Dimensões" },
  { field: "largura",          label: "Largura",              group: "Dimensões" },
  { field: "tipo",             label: "Tipo",                 group: "" },
  { field: "estado_conservacao", label: "Estado de Conservação", group: "" },
  { field: "ambiente",         label: "Ambiente",             group: "" },
];

// All available unmapped fields (available to drag into the table)
const ALL_AVAILABLE_FIELDS: ColumnDef[] = [
  { field: "inspection_date",  label: "Data Insp.",    group: "" },
  { field: "identificacao",    label: "Identificação", group: "" },
  { field: "material",         label: "Material",      group: "" },
  { field: "reparar",          label: "Reparar",       group: "" },
  { field: "limpeza",          label: "Limpeza",       group: "" },
  { field: "limpeza_extensao", label: "Ext. Limpeza",  group: "" },
  { field: "implantar",        label: "Implantar",     group: "" },
];

function isDefaultColumns(columns: ColumnDef[]): boolean {
  if (columns.length !== DEFAULT_COLUMNS.length) return false;
  return columns.every((c, i) => c.field === DEFAULT_COLUMNS[i].field);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ResultsPanel({ result, onReset }: ResultsPanelProps) {
  const [columns, setColumns] = useState<ColumnDef[]>(DEFAULT_COLUMNS);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const records: DrainageRecordData[] = result.records ?? [];

  // Fields not currently in the active columns
  const unmappedFields = ALL_AVAILABLE_FIELDS.filter(
    (f) => !columns.some((c) => c.field === f.field)
  );

  const handleColumnsChange = (next: ColumnDef[]) => {
    setColumns(next);
    setDownloadError(null);
  };

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      if (isDefaultColumns(columns) && result.excel_base64) {
        // Use pre-generated Excel — no extra request needed
        const byteChars = atob(result.excel_base64);
        const bytes = new Uint8Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i);
        const blob = new Blob([bytes], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });
        downloadBlob(blob, "drenagem_consolidado.xlsx");
      } else {
        // Custom column set — ask backend to regenerate
        const blob = await generateExcelCustom(records, columns);
        downloadBlob(blob, "drenagem_consolidado.xlsx");
      }
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : "Erro ao baixar Excel");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Two-pane layout: table + unmapped fields sidebar */}
      <div className="flex gap-4 items-start">
        {/* Preview table — takes all remaining width */}
        <div className="min-w-0 flex-1">
          <ExcelPreviewTable
            columns={columns}
            records={records}
            onColumnsChange={handleColumnsChange}
          />
        </div>

        {/* Unmapped fields sidebar */}
        <div className="w-48 shrink-0">
          <UnmappedFieldsPanel fields={unmappedFields} records={records} />
        </div>
      </div>

      {/* Action bar */}
      {downloadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {downloadError}
        </div>
      )}

      <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-6 py-4">
        <p className="text-sm text-gray-600">
          <span className="font-medium text-gray-800">{result.successful_files}</span>{" "}
          arquivo{result.successful_files !== 1 ? "s" : ""} processado
          {result.successful_files !== 1 ? "s" : ""} com sucesso
          {!isDefaultColumns(columns) && (
            <span className="ml-2 rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700 font-medium">
              colunas personalizadas
            </span>
          )}
        </p>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
          >
            <RefreshCw className="h-4 w-4" />
            Novo Lote
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading || columns.length === 0}
            className="flex items-center gap-2 rounded-lg bg-success px-5 py-2.5 text-sm font-medium text-white shadow transition-colors hover:bg-green-600 disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            {downloading ? "Gerando..." : "Baixar Excel"}
          </button>
        </div>
      </div>
    </div>
  );
}
