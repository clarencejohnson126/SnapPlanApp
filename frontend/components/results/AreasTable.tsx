"use client";

import { clsx } from "clsx";

export interface AreaResult {
  id: string;
  room_id: string;
  room_name: string | null;
  room_type: string | null;
  area_m2: number;
  area_factor: number;
  effective_area_m2: number | null;
  source_text: string | null;
  source_page: number;
  source_bbox: Record<string, number> | null;
  confidence: number;
}

interface AreasTableProps {
  areas: AreaResult[];
  selectedId: string | null;
  onSelect: (area: AreaResult) => void;
}

// Format number with German locale
function formatNumber(value: number, decimals: number = 2): string {
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Room type badge
function RoomTypeBadge({ type }: { type: string | null }) {
  if (!type) return null;

  const styles: Record<string, string> = {
    residential: "bg-[#3B82F6]/10 text-[#3B82F6]",
    balcony: "bg-[#F59E0B]/10 text-[#F59E0B]",
    circulation: "bg-[#A855F7]/10 text-[#A855F7]",
    utility: "bg-[#64748B]/10 text-[#64748B]",
    technical: "bg-[#EF4444]/10 text-[#EF4444]",
  };

  return (
    <span
      className={clsx(
        "px-2 py-0.5 rounded text-xs font-medium capitalize",
        styles[type] || styles.utility
      )}
    >
      {type}
    </span>
  );
}

export function AreasTable({ areas, selectedId, onSelect }: AreasTableProps) {
  if (areas.length === 0) {
    return (
      <div className="bg-[#1A2942] rounded-xl border border-white/5 p-12 text-center">
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
            d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
          />
        </svg>
        <p className="text-[#94A3B8]">No areas extracted</p>
        <p className="text-[#64748B] text-sm mt-1">
          The analysis did not find any NRF values
        </p>
      </div>
    );
  }

  return (
    <div className="bg-[#1A2942] rounded-xl border border-white/5 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/5">
              <th className="text-left text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Room Name
              </th>
              <th className="text-left text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Code
              </th>
              <th className="text-left text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Type
              </th>
              <th className="text-right text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Area m²
              </th>
              <th className="text-right text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Counted m²
              </th>
              <th className="text-center text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Factor
              </th>
              <th className="text-center text-xs font-medium text-[#64748B] uppercase tracking-wider px-6 py-4">
                Page
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {areas.map((area) => {
              const isSelected = selectedId === area.id;
              const isFactored = area.area_factor !== 1.0;
              const effectiveArea =
                area.effective_area_m2 ?? area.area_m2 * area.area_factor;

              return (
                <tr
                  key={area.id}
                  onClick={() => onSelect(area)}
                  className={clsx(
                    "cursor-pointer transition-colors",
                    isSelected
                      ? "bg-[#00D4AA]/10"
                      : "hover:bg-white/[0.02]"
                  )}
                >
                  <td className="px-6 py-4 text-sm text-white">
                    {area.room_name || "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-[#94A3B8] font-mono">
                    {area.room_id}
                  </td>
                  <td className="px-6 py-4">
                    <RoomTypeBadge type={area.room_type} />
                  </td>
                  <td className="px-6 py-4 text-sm text-white font-mono text-right">
                    {formatNumber(area.area_m2)}
                  </td>
                  <td
                    className={clsx(
                      "px-6 py-4 text-sm font-mono text-right",
                      isFactored ? "text-[#F59E0B]" : "text-[#00D4AA]"
                    )}
                  >
                    {formatNumber(effectiveArea)}
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span
                      className={clsx(
                        "px-2 py-0.5 rounded text-xs font-mono",
                        isFactored
                          ? "bg-[#F59E0B]/10 text-[#F59E0B]"
                          : "bg-white/5 text-[#64748B]"
                      )}
                    >
                      {area.area_factor.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-[#64748B] text-center font-mono">
                    {area.source_page}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
