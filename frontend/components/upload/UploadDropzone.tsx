"use client";

import { useCallback, useState } from "react";
import { clsx } from "clsx";

interface UploadDropzoneProps {
  onFileSelect: (file: File) => void;
  isUploading?: boolean;
  accept?: string;
}

export function UploadDropzone({
  onFileSelect,
  isUploading = false,
  accept = ".pdf",
}: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      const pdfFile = files.find(
        (file) => file.type === "application/pdf" || file.name.endsWith(".pdf")
      );

      if (pdfFile) {
        onFileSelect(pdfFile);
      }
    },
    [onFileSelect]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        onFileSelect(files[0]);
      }
    },
    [onFileSelect]
  );

  return (
    <div
      className={clsx(
        "relative border-2 border-dashed rounded-xl p-12 text-center transition-colors",
        isDragOver
          ? "border-[#00D4AA] bg-[#00D4AA]/5"
          : "border-white/20 hover:border-white/40",
        isUploading && "pointer-events-none opacity-60"
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        type="file"
        accept={accept}
        onChange={handleFileInput}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        disabled={isUploading}
      />

      <div className="flex flex-col items-center">
        {/* Icon */}
        <div
          className={clsx(
            "w-16 h-16 rounded-full flex items-center justify-center mb-6",
            isDragOver ? "bg-[#00D4AA]/20" : "bg-[#1A2942]"
          )}
        >
          {isUploading ? (
            <svg
              className="w-8 h-8 text-[#00D4AA] animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ) : (
            <svg
              className={clsx(
                "w-8 h-8",
                isDragOver ? "text-[#00D4AA]" : "text-[#94A3B8]"
              )}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
              />
            </svg>
          )}
        </div>

        {/* Text */}
        <h3
          className={clsx(
            "text-lg font-medium mb-2",
            isDragOver ? "text-[#00D4AA]" : "text-white"
          )}
        >
          {isUploading
            ? "Uploading..."
            : isDragOver
              ? "Drop to upload"
              : "Drop PDF here or click to browse"}
        </h3>

        <p className="text-sm text-[#64748B]">
          Support for CAD-exported floor plans (PDF format)
        </p>
      </div>
    </div>
  );
}
