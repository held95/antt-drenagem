import type { ColumnDef, DrainageRecordData, ProcessResponse } from "../types";

const BASE = "/api";

export async function processFiles(files: File[]): Promise<ProcessResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`${BASE}/process`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro no processamento" }));
    throw new Error(err.detail || `Erro ${res.status}`);
  }

  return res.json();
}

export async function generateExcelCustom(
  records: DrainageRecordData[],
  columns: ColumnDef[],
): Promise<Blob> {
  const res = await fetch(`${BASE}/generate-excel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ records, columns }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao gerar Excel" }));
    throw new Error(err.detail || `Erro ${res.status}`);
  }

  return res.blob();
}
