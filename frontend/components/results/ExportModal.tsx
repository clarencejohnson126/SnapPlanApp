"use client";

import { useState } from "react";
import { clsx } from "clsx";

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExport: (format: string) => void;
  isExporting?: boolean;
}

interface ExportOption {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  disabled?: boolean;
  comingSoon?: boolean;
}

const exportOptions: ExportOption[] = [
  {
    id: "json",
    label: "JSON",
    description: "Raw data with full audit trail",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    ),
  },
  {
    id: "excel",
    label: "Excel",
    description: "Formatted spreadsheet with formulas",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    disabled: true,
    comingSoon: true,
  },
  {
    id: "pdf",
    label: "PDF Report",
    description: "Professional report with summary",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
    disabled: true,
    comingSoon: true,
  },
];

export function ExportModal({
  isOpen,
  onClose,
  onExport,
  isExporting,
}: ExportModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<string>("json");

  if (!isOpen) return null;

  const handleExport = () => {
    onExport(selectedFormat);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="bg-[#1A2942] rounded-xl border border-white/10 shadow-xl max-w-md w-full"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
            <h2 className="text-lg font-semibold text-white">Export Results</h2>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-[#64748B] hover:text-white hover:bg-white/5 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            <p className="text-sm text-[#94A3B8] mb-4">
              Choose an export format for your analysis results
            </p>

            {/* Format options */}
            <div className="space-y-3">
              {exportOptions.map((option) => (
                <button
                  key={option.id}
                  onClick={() => !option.disabled && setSelectedFormat(option.id)}
                  disabled={option.disabled}
                  className={clsx(
                    "w-full flex items-center gap-4 p-4 rounded-lg border transition-colors text-left",
                    selectedFormat === option.id && !option.disabled
                      ? "border-[#00D4AA] bg-[#00D4AA]/5"
                      : option.disabled
                        ? "border-white/5 opacity-50 cursor-not-allowed"
                        : "border-white/10 hover:border-white/20"
                  )}
                >
                  <div
                    className={clsx(
                      "w-10 h-10 rounded-lg flex items-center justify-center",
                      selectedFormat === option.id && !option.disabled
                        ? "bg-[#00D4AA]/10 text-[#00D4AA]"
                        : "bg-white/5 text-[#94A3B8]"
                    )}
                  >
                    {option.icon}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{option.label}</span>
                      {option.comingSoon && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-[#64748B]/20 text-[#64748B]">
                          Coming Soon
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-[#64748B]">{option.description}</p>
                  </div>
                  {selectedFormat === option.id && !option.disabled && (
                    <svg
                      className="w-5 h-5 text-[#00D4AA]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/5">
            <button
              onClick={onClose}
              className="px-4 py-2.5 rounded-lg text-[#94A3B8] hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={isExporting || !selectedFormat}
              className="px-4 py-2.5 rounded-lg bg-[#00D4AA] text-[#0F1B2A] font-semibold hover:bg-[#00D4AA]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {isExporting ? (
                <>
                  <svg
                    className="w-4 h-4 animate-spin"
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
                  Exporting...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
