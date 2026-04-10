import { FileSpreadsheet } from "lucide-react";

export function Header() {
  return (
    <header className="bg-primary text-white shadow-md">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-4">
        <FileSpreadsheet className="h-8 w-8 text-accent" />
        <div>
          <h1 className="text-xl font-bold tracking-tight">
            ANTT Drenagem — Consolidador
          </h1>
          <p className="text-sm text-white/70">
            Processe PDFs de monitoração e gere um Excel consolidado
          </p>
        </div>
      </div>
    </header>
  );
}
