import type { JobStatus, UploadResponse } from "../types";

const BASE = "/api";

export async function uploadPdfs(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro no upload" }));
    throw new Error(err.detail || `Erro ${res.status}`);
  }

  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE}/status/${jobId}`);

  if (!res.ok) {
    throw new Error(`Erro ao consultar status: ${res.status}`);
  }

  return res.json();
}

export async function downloadExcel(jobId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/download/${jobId}`);

  if (!res.ok) {
    throw new Error("Erro ao baixar Excel");
  }

  return res.blob();
}
