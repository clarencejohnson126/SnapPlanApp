"use client";

interface TotalsCardProps {
  totalRooms: number;
  totalAreaM2: number;
  effectiveAreaM2: number;
  balconyFactor: number;
}

// Format number with German locale
function formatNumber(value: number, decimals: number = 2): string {
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function TotalsCard({
  totalRooms,
  totalAreaM2,
  effectiveAreaM2,
  balconyFactor,
}: TotalsCardProps) {
  const hasFactoredAreas = totalAreaM2 !== effectiveAreaM2;

  return (
    <div className="bg-[#1A2942] rounded-xl border border-white/5 p-6">
      <h2 className="text-lg font-semibold text-white mb-6">Summary</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Area */}
        <div>
          <p className="text-sm text-[#94A3B8] mb-1">Total Area</p>
          <p className="text-2xl font-bold text-white font-mono">
            {formatNumber(totalAreaM2)}
            <span className="text-sm text-[#64748B] ml-1">m²</span>
          </p>
        </div>

        {/* Counted Area */}
        <div>
          <p className="text-sm text-[#94A3B8] mb-1">Counted Area</p>
          <p className="text-2xl font-bold text-[#00D4AA] font-mono">
            {formatNumber(effectiveAreaM2)}
            <span className="text-sm text-[#64748B] ml-1">m²</span>
          </p>
          {hasFactoredAreas && (
            <p className="text-xs text-[#64748B] mt-1">
              After balcony factor applied
            </p>
          )}
        </div>

        {/* Rooms */}
        <div>
          <p className="text-sm text-[#94A3B8] mb-1">Total Rooms</p>
          <p className="text-2xl font-bold text-white font-mono">{totalRooms}</p>
        </div>
      </div>

      {/* Balcony factor indicator */}
      {hasFactoredAreas && (
        <div className="mt-6 pt-4 border-t border-white/5">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[#94A3B8]">Balcony Factor:</span>
            <span className="px-2 py-0.5 rounded bg-[#F59E0B]/10 text-[#F59E0B] font-mono">
              {balconyFactor}
            </span>
            <span className="text-[#64748B]">
              (applied to Balkon, Terrasse, Loggia)
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
