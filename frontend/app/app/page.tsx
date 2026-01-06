import Link from "next/link";

// Stats card component
function StatCard({
  label,
  value,
  subtitle,
}: {
  label: string;
  value: string | number;
  subtitle?: string;
}) {
  return (
    <div className="bg-[#1A2942] rounded-xl p-6 border border-white/5">
      <p className="text-[#94A3B8] text-sm font-medium">{label}</p>
      <p className="text-3xl font-bold text-white mt-2 font-mono">{value}</p>
      {subtitle && <p className="text-[#64748B] text-xs mt-1">{subtitle}</p>}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Welcome header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Welcome to SnapPlan
        </h1>
        <p className="text-[#94A3B8] mt-1">
          Extract room areas from construction documents instantly
        </p>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          href="/app/scan"
          className="group bg-gradient-to-br from-[#00D4AA]/10 to-[#00D4AA]/5 rounded-xl border border-[#00D4AA]/20 hover:border-[#00D4AA]/40 p-8 transition-all"
        >
          <div className="w-16 h-16 rounded-2xl bg-[#00D4AA]/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
            <svg
              className="w-8 h-8 text-[#00D4AA]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">Quick Scan</h2>
          <p className="text-[#94A3B8]">
            Upload a floor plan PDF and extract room areas instantly. Get results in seconds with full traceability.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 text-[#00D4AA] font-medium">
            Start Scanning
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </div>
        </Link>

        <div className="bg-[#1A2942] rounded-xl border border-white/5 p-8">
          <div className="w-16 h-16 rounded-2xl bg-[#3B82F6]/20 flex items-center justify-center mb-6">
            <svg
              className="w-8 h-8 text-[#3B82F6]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">How It Works</h2>
          <ol className="text-[#94A3B8] space-y-2 list-decimal list-inside">
            <li>Upload your CAD-exported PDF floor plan</li>
            <li>SnapPlan extracts room areas automatically</li>
            <li>Review results with full audit trail</li>
            <li>Export to Excel, CSV, or PDF</li>
          </ol>
        </div>
      </div>

      {/* Features */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Supported Formats</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#1A2942] rounded-xl border border-white/5 p-5">
            <code className="text-[#00D4AA] font-mono text-lg">NRF:</code>
            <p className="text-[#94A3B8] text-sm mt-2">Netto-Raumfläche (Office buildings)</p>
          </div>
          <div className="bg-[#1A2942] rounded-xl border border-white/5 p-5">
            <code className="text-[#00D4AA] font-mono text-lg">F:</code>
            <p className="text-[#94A3B8] text-sm mt-2">Fläche (Residential buildings)</p>
          </div>
          <div className="bg-[#1A2942] rounded-xl border border-white/5 p-5">
            <code className="text-[#00D4AA] font-mono text-lg">NGF:</code>
            <p className="text-[#94A3B8] text-sm mt-2">Netto-Grundfläche (Highrise)</p>
          </div>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Extraction Method" value="Text-based" subtitle="100% deterministic" />
        <StatCard label="Balcony Factor" value="50%" subtitle="auto-applied" />
        <StatCard label="Export Formats" value="3" subtitle="Excel, CSV, PDF" />
      </div>
    </div>
  );
}
