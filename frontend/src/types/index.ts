export interface FileResult {
  filename: string;
  status: string;
  warnings: string[];
  error: string | null;
}

export interface DrainageRecordData {
  source_filename: string;
  inspection_date: string | null;
  identificacao: string | null;
  estaca_inicio: string | null;
  km_inicial: string | null;
  latitude_inicio: number | null;
  longitude_inicio: number | null;
  estaca_fim: string | null;
  km_final: string | null;
  latitude_fim: number | null;
  longitude_fim: number | null;
  largura: number | null;
  altura: number | null;
  extensao: number | null;
  tipo: string | null;
  estado_conservacao: string | null;
  material: string | null;
  ambiente: string | null;
  reparar: boolean | null;
  limpeza: boolean | null;
  limpeza_extensao: number | null;
  implantar: boolean | null;
  confidence: number;
}

export interface ColumnDef {
  field: string;
  label: string;
  group: string;
}

export interface ProcessResponse {
  total_files: number;
  successful_files: number;
  files: FileResult[];
  excel_base64: string | null;
  records: DrainageRecordData[];
}

export type AppState = "idle" | "processing" | "completed" | "error";
