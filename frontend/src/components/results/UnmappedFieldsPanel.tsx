import type { ColumnDef, DrainageRecordData } from "../../types";

interface UnmappedFieldsPanelProps {
  fields: ColumnDef[];
  records: DrainageRecordData[];
}

function getSampleValue(field: string, records: DrainageRecordData[]): string {
  for (const r of records) {
    const v = r[field as keyof DrainageRecordData];
    if (v !== null && v !== undefined) {
      if (typeof v === "boolean") return v ? "Sim" : "Não";
      return String(v);
    }
  }
  return "—";
}

export function UnmappedFieldsPanel({ fields, records }: UnmappedFieldsPanelProps) {
  function handleDragStart(e: React.DragEvent, col: ColumnDef) {
    e.dataTransfer.setData("columnDef", JSON.stringify(col));
    e.dataTransfer.effectAllowed = "copy";
  }

  if (fields.length === 0) {
    return (
      <div className="flex h-full flex-col rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">
          Campos disponíveis
        </h3>
        <p className="text-xs text-gray-400 italic">
          Todos os campos já estão nas colunas.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="mb-1 text-sm font-semibold text-gray-700">
        Campos disponíveis
      </h3>
      <p className="mb-3 text-xs text-gray-400">
        Arraste para adicionar ao Excel
      </p>
      <div className="flex flex-col gap-2 overflow-y-auto">
        {fields.map((col) => {
          const sample = getSampleValue(col.field, records);
          return (
            <div
              key={col.field}
              draggable
              onDragStart={(e) => handleDragStart(e, col)}
              className="cursor-grab rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 select-none hover:bg-blue-100 active:cursor-grabbing transition-colors"
              title="Arraste para a tabela para adicionar como coluna"
            >
              <p className="text-xs font-semibold text-blue-800">{col.label}</p>
              <p className="mt-0.5 text-xs text-blue-500 truncate">
                ex: {sample}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
