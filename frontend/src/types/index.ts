export interface UploadResponse {
  job_id: string;
  file_count: number;
  status: string;
}

export interface FileResult {
  filename: string;
  status: string;
  warnings: string[];
  error: string | null;
}

export interface JobStatus {
  job_id: string;
  status: string;
  total_files: number;
  processed_files: number;
  files: FileResult[];
  download_ready: boolean;
}

export type AppState = "idle" | "uploading" | "processing" | "completed" | "error";
