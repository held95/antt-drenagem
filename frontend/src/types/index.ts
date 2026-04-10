export interface FileResult {
  filename: string;
  status: string;
  warnings: string[];
  error: string | null;
}

export interface ProcessResponse {
  total_files: number;
  successful_files: number;
  files: FileResult[];
  excel_base64: string | null;
}

export type AppState = "idle" | "processing" | "completed" | "error";
