import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText } from "lucide-react";
import { cn } from "../../lib/cn";

interface DropZoneProps {
  onFilesAdded: (files: File[]) => void;
  disabled?: boolean;
}

export function DropZone({ onFilesAdded, disabled }: DropZoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const valid = acceptedFiles.filter((f) => {
        const name = f.name.toLowerCase();
        return (
          name.endsWith(".pdf") ||
          name.endsWith(".jpg") ||
          name.endsWith(".jpeg") ||
          name.endsWith(".png") ||
          name.endsWith(".webp")
        );
      });
      if (valid.length > 0) {
        onFilesAdded(valid);
      }
    },
    [onFilesAdded]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    },
    disabled,
    multiple: true,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-all",
        isDragActive
          ? "border-accent bg-accent/10"
          : "border-gray-300 bg-white hover:border-primary/40 hover:bg-primary/5",
        disabled && "pointer-events-none opacity-50"
      )}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {isDragActive ? (
          <FileText className="h-12 w-12 text-accent" />
        ) : (
          <Upload className="h-12 w-12 text-gray-400" />
        )}
        <p className="text-lg font-medium text-gray-700">
          {isDragActive
            ? "Solte os arquivos aqui..."
            : "Arraste PDFs ou imagens aqui ou clique para selecionar"}
        </p>
        <p className="text-sm text-gray-500">
          Arquivos .pdf, .jpg, .jpeg, .png — sem limite de quantidade
        </p>
      </div>
    </div>
  );
}
