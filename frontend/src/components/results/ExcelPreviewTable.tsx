import { X } from "lucide-react";
import type { ColumnDef, DrainageRecordData } from "../../types";

interface ExcelPreviewTableProps {
  columns: ColumnDef[];
  records: DrainageRecordData[];
  onColumnsChange: (cols: ColumnDef[]) => void;
}

const MAX_ROWS = 50;

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (typeof value === "number") return value.toString();
  return String(value);
}

export function ExcelPreviewTable({
  columns,
  records,
  onColumnsChange,
}: ExcelPreviewTableProps) {
  const displayRecords = records.slice(0, MAX_ROWS);

  // Drag state for column reordering
  function handleHeaderDragStart(e: React.DragEvent, colIndex: number) {
    e.dataTransfer.setData("reorderColIndex", String(colIndex));
    e.dataTransfer.effectAllowed = "move";
  }

  function handleHeaderDrop(e: React.DragEvent, targetIndex: number) {
    e.preventDefault();
    const sourceIndexStr = e.dataTransfer.getData("reorderColIndex");
    if (sourceIndexStr === "") return; // came from unmapped panel, handled by drop zone
    const sourceIndex = parseInt(sourceIndexStr, 10);
    if (isNaN(sourceIndex) || sourceIndex === targetIndex) return;
    const next = [...columns];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    onColumnsChange(next);
  }

  function handleHeaderDragOver(e: React.DragEvent) {
    // Only allow if it's a reorder drag (not from unmapped panel)
    if (e.dataTransfer.types.includes("reordercolindex")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
    }
  }

  function handleRemoveColumn(colIndex: number) {
    onColumnsChange(columns.filter((_, i) => i !== colIndex));
  }

  // Drop zone for new columns (at the end of headers)
  function handleDropZoneDragOver(e: React.DragEvent) {
    if (e.dataTransfer.types.includes("columndef")) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  }

  function handleDropZoneDrop(e: React.DragEvent) {
    e.preventDefault();
    const raw = e.dataTransfer.getData("columnDef");
    if (!raw) return;
    try {
      const col: ColumnDef = JSON.parse(raw);
      if (columns.some((c) => c.field === col.field)) return;
      onColumnsChange([...columns, col]);
    } catch {
      // ignore malformed data
    }
  }

  // Group header spans — consecutive columns with the same non-empty group
  const groupSpans: { label: string; start: number; span: number }[] = [];
  let i = 0;
  while (i < columns.length) {
    const g = columns[i].group;
    if (!g) {
      groupSpans.push({ label: "", start: i, span: 1 });
      i++;
    } else {
      let j = i + 1;
      while (j < columns.length && columns[j].group === g) j++;
      groupSpans.push({ label: g, start: i, span: j - i });
      i = j;
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Row counter */}
      <p className="text-xs text-gray-500">
        Mostrando {displayRecords.length} de {records.length} registro
        {records.length !== 1 ? "s" : ""}
        {records.length > MAX_ROWS && ` (primeiros ${MAX_ROWS})`}
      </p>

      {/* Scrollable table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="min-w-max border-collapse text-xs">
          <thead>
            {/* Row 1 — group labels */}
            <tr>
              {groupSpans.map((gs, idx) =>
                gs.label ? (
                  <th
                    key={idx}
                    colSpan={gs.span}
                    className="border border-gray-300 bg-[#D9D9D9] px-2 py-1 text-center font-bold text-gray-800"
                  >
                    {gs.label}
                  </th>
                ) : (
                  <th
                    key={idx}
                    rowSpan={2}
                    draggable
                    onDragStart={(e) => handleHeaderDragStart(e, gs.start)}
                    onDragOver={handleHeaderDragOver}
                    onDrop={(e) => handleHeaderDrop(e, gs.start)}
                    className="group relative border border-gray-300 bg-[#D9D9D9] px-2 py-1 text-center font-bold text-gray-800 cursor-grab select-none"
                  >
                    <span>{columns[gs.start].label}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveColumn(gs.start)}
                      className="absolute right-0.5 top-0.5 hidden rounded p-0.5 text-gray-500 hover:bg-red-100 hover:text-red-600 group-hover:flex"
                      title="Remover coluna"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </th>
                )
              )}
              {/* Drop zone cell */}
              <th
                rowSpan={2}
                onDragOver={handleDropZoneDragOver}
                onDrop={handleDropZoneDrop}
                className="border border-dashed border-blue-300 bg-blue-50 px-3 py-1 text-center text-blue-400 select-none min-w-[80px]"
              >
                + Coluna
              </th>
            </tr>

            {/* Row 2 — sub-headers (only for grouped columns) */}
            <tr>
              {columns.map((col, colIdx) => {
                if (!col.group) return null; // already rendered with rowSpan=2
                return (
                  <th
                    key={colIdx}
                    draggable
                    onDragStart={(e) => handleHeaderDragStart(e, colIdx)}
                    onDragOver={handleHeaderDragOver}
                    onDrop={(e) => handleHeaderDrop(e, colIdx)}
                    className="group relative border border-gray-300 bg-[#D9D9D9] px-2 py-1 text-center font-semibold text-gray-700 cursor-grab select-none whitespace-nowrap"
                  >
                    <span>{col.label}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveColumn(colIdx)}
                      className="absolute right-0.5 top-0.5 hidden rounded p-0.5 text-gray-500 hover:bg-red-100 hover:text-red-600 group-hover:flex"
                      title="Remover coluna"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody>
            {displayRecords.map((record, rowIdx) => (
              <tr
                key={rowIdx}
                className={rowIdx % 2 === 0 ? "bg-white" : "bg-gray-50"}
              >
                {columns.map((col, colIdx) => (
                  <td
                    key={colIdx}
                    className="border border-gray-200 px-2 py-1 text-center text-gray-700 whitespace-nowrap"
                  >
                    {formatValue(record[col.field as keyof DrainageRecordData])}
                  </td>
                ))}
                {/* Empty cell under the drop zone column */}
                <td className="border border-dashed border-blue-100 bg-blue-50/30" />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
