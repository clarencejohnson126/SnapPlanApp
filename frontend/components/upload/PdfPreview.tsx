"use client";

import { useState } from "react";

interface PdfPreviewProps {
  file: File;
  onRemove: () => void;
}

// Format file size
function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function PdfPreview({ file, onRemove }: PdfPreviewProps) {
  const [pageCount] = useState<number>(1); // Would be extracted from PDF
  const [currentPage] = useState(1);

  return (
    <div className="bg-[#1A2942] rounded-xl border border-white/5 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#00D4AA]/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-[#00D4AA]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-white truncate max-w-[200px]">
              {file.name}
            </p>
            <p className="text-xs text-[#64748B]">{formatFileSize(file.size)}</p>
          </div>
        </div>
        <button
          onClick={onRemove}
          className="p-2 rounded-lg text-[#64748B] hover:text-white hover:bg-white/5 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Preview area */}
      <div className="aspect-[4/3] bg-[#0F1B2A] relative flex items-center justify-center">
        {/* Blueprint grid pattern */}
        <div
          className="absolute inset-0 opacity-5"
          style={{
            backgroundImage: `
              linear-gradient(rgba(0, 212, 170, 0.8) 1px, transparent 1px),
              linear-gradient(90deg, rgba(0, 212, 170, 0.8) 1px, transparent 1px)
            `,
            backgroundSize: "30px 30px",
          }}
        />

        {/* Placeholder for actual PDF preview */}
        <div className="text-center relative z-10">
          <svg className="w-16 h-16 text-[#00D4AA]/30 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-sm text-[#64748B]">PDF Preview</p>
        </div>
      </div>

      {/* Footer - Page navigation */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-white/5">
        <button
          disabled={currentPage <= 1}
          className="p-1.5 rounded-lg text-[#94A3B8] hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <span className="text-sm text-[#94A3B8]">
          Page {currentPage} of {pageCount}
        </span>
        <button
          disabled={currentPage >= pageCount}
          className="p-1.5 rounded-lg text-[#94A3B8] hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}
