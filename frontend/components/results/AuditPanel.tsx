"use client";

import { clsx } from "clsx";
import type { AreaResult } from "./AreasTable";

interface AuditPanelProps {
  area: AreaResult | null;
  isOpen: boolean;
  onClose: () => void;
}

// Format number with German locale
function formatNumber(value: number, decimals: number = 2): string {
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Confidence indicator
function ConfidenceIndicator({ confidence }: { confidence: number }) {
  const percentage = Math.round(confidence * 100);
  const colorClass =
    percentage >= 90
      ? "text-[#00D4AA]"
      : percentage >= 70
        ? "text-[#F59E0B]"
        : "text-red-400";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-[#0F1B2A] rounded-full overflow-hidden">
        <div
          className={clsx(
            "h-full rounded-full",
            percentage >= 90
              ? "bg-[#00D4AA]"
              : percentage >= 70
                ? "bg-[#F59E0B]"
                : "bg-red-400"
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className={clsx("text-sm font-mono", colorClass)}>{percentage}%</span>
    </div>
  );
}

export function AuditPanel({ area, isOpen, onClose }: AuditPanelProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 lg:hidden"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className={clsx(
          "fixed right-0 top-0 bottom-0 w-80 bg-[#1A2942] border-l border-white/5 z-50",
          "transform transition-transform duration-300 ease-in-out",
          "lg:relative lg:transform-none",
          isOpen ? "translate-x-0" : "translate-x-full lg:translate-x-0"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <h3 className="font-semibold text-white">Audit Trail</h3>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-[#64748B] hover:text-white hover:bg-white/5 transition-colors lg:hidden"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto h-[calc(100%-60px)]">
          {area ? (
            <>
              {/* Selected room info */}
              <div>
                <p className="text-xs text-[#64748B] uppercase tracking-wider mb-2">
                  Selected
                </p>
                <p className="text-lg font-semibold text-white">
                  {area.room_name || area.room_id}
                </p>
                <p className="text-sm text-[#94A3B8] font-mono">{area.room_id}</p>
              </div>

              {/* Source text */}
              <div>
                <p className="text-xs text-[#64748B] uppercase tracking-wider mb-2">
                  Source Text
                </p>
                <div className="p-3 rounded-lg bg-[#0F1B2A] border border-white/5">
                  <code className="text-sm text-[#00D4AA] font-mono">
                    {area.source_text || "No source text available"}
                  </code>
                </div>
                <p className="text-xs text-[#64748B] mt-1">
                  Raw text extracted from PDF
                </p>
              </div>

              {/* Page number */}
              <div>
                <p className="text-xs text-[#64748B] uppercase tracking-wider mb-2">
                  Page Number
                </p>
                <p className="text-lg font-mono text-white">{area.source_page}</p>
              </div>

              {/* Bounding box */}
              {area.source_bbox && (
                <div>
                  <p className="text-xs text-[#64748B] uppercase tracking-wider mb-2">
                    Bounding Box
                  </p>
                  <div className="p-3 rounded-lg bg-[#0F1B2A] border border-white/5">
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div>
                        <span className="text-[#64748B]">x: </span>
                        <span className="text-white">
                          {area.source_bbox.x?.toFixed(1) ?? "-"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[#64748B]">y: </span>
                        <span className="text-white">
                          {area.source_bbox.y?.toFixed(1) ?? "-"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[#64748B]">w: </span>
                        <span className="text-white">
                          {area.source_bbox.width?.toFixed(1) ?? "-"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[#64748B]">h: </span>
                        <span className="text-white">
                          {area.source_bbox.height?.toFixed(1) ?? "-"}
                        </span>
                      </div>
                    </div>
                  </div>
                  {/* Visual bbox preview placeholder */}
                  <div className="mt-3 aspect-video bg-[#0F1B2A] rounded-lg relative overflow-hidden">
                    <div
                      className="absolute inset-0 opacity-10"
                      style={{
                        backgroundImage: `
                          linear-gradient(rgba(0, 212, 170, 0.5) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(0, 212, 170, 0.5) 1px, transparent 1px)
                        `,
                        backgroundSize: "20px 20px",
                      }}
                    />
                    <div className="absolute inset-4 border-2 border-dashed border-[#00D4AA]/50 rounded" />
                    <p className="absolute bottom-2 left-2 text-xs text-[#64748B]">
                      BBox preview
                    </p>
                  </div>
                </div>
              )}

              {/* Confidence */}
              <div>
                <p className="text-xs text-[#64748B] uppercase tracking-wider mb-2">
                  Confidence
                </p>
                <ConfidenceIndicator confidence={area.confidence} />
              </div>

              {/* Area details */}
              <div>
                <p className="text-xs text-[#64748B] uppercase tracking-wider mb-2">
                  Area Details
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[#94A3B8]">Raw Area</span>
                    <span className="text-white font-mono">
                      {formatNumber(area.area_m2)} m²
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#94A3B8]">Factor</span>
                    <span className="text-[#F59E0B] font-mono">
                      ×{area.area_factor.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-white/5 pt-2">
                    <span className="text-[#94A3B8]">Effective Area</span>
                    <span className="text-[#00D4AA] font-mono font-semibold">
                      {formatNumber(
                        area.effective_area_m2 ?? area.area_m2 * area.area_factor
                      )}{" "}
                      m²
                    </span>
                  </div>
                </div>
              </div>

              {/* View in PDF button (placeholder) */}
              <button
                className="w-full py-2.5 px-4 rounded-lg border border-white/10 text-[#94A3B8] hover:text-white hover:border-white/20 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                disabled
              >
                View in PDF (Coming Soon)
              </button>
            </>
          ) : (
            <div className="text-center py-12">
              <svg
                className="w-12 h-12 text-[#64748B] mx-auto mb-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"
                />
              </svg>
              <p className="text-[#94A3B8]">No area selected</p>
              <p className="text-[#64748B] text-sm mt-1">
                Click a row to see audit details
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
