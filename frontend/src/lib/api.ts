import type { ProcessResponse } from "../types";

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
