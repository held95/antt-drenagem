import { FileText, Trash2, X } from "lucide-react";

interface FileListProps {
  files: File[];
  onRemove: (index: number) => void;
  onClearAll: () => void;
  disabled?: boolean;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileList({ files, onRemove, onClearAll, disabled }: FileListProps) {
  if (files.length === 0) return null;

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2">
        <span className="text-sm font-medium text-gray-700">
          {files.length} arquivo{files.length > 1 ? "s" : ""} ({formatSize(totalSize)} total)
        </span>
        {!disabled && files.length > 1 && (
          <button
            onClick={onClearAll}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-danger"
          >
            <Trash2 className="h-3 w-3" />
            Limpar todos
          </button>
        )}
      </div>
      <ul className="max-h-60 divide-y divide-gray-50 overflow-y-auto">
        {files.map((file, idx) => (
          <li
            key={`${file.name}-${idx}`}
            className="flex items-center gap-3 px-4 py-2"
          >
            <FileText className="h-4 w-4 shrink-0 text-primary" />
            <span className="min-w-0 flex-1 truncate text-sm text-gray-700">
              {file.name}
            </span>
            <span className="shrink-0 text-xs text-gray-400">
              {formatSize(file.size)}
            </span>
            {!disabled && (
              <button
                onClick={() => onRemove(idx)}
                className="shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-danger"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
