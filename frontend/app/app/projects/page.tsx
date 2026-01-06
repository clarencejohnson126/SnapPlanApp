import Link from "next/link";

export default function ProjectsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Projects</h1>
          <p className="text-[#94A3B8] mt-1">
            Manage your construction document projects
          </p>
        </div>
      </div>

      {/* Demo mode notice */}
      <div className="bg-[#1A2942] rounded-xl border border-white/5 p-12 text-center">
        <div className="w-16 h-16 rounded-full bg-[#3B82F6]/10 flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-[#3B82F6]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white mb-2">
          Project Management Coming Soon
        </h2>
        <p className="text-[#94A3B8] max-w-md mx-auto mb-8">
          In the full version, you&apos;ll be able to organize floor plans into projects for easy management. For now, use Quick Scan for instant analysis.
        </p>

        <Link
          href="/app/scan"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#00D4AA] text-[#0F1B2A] font-semibold hover:bg-[#00D4AA]/90 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Go to Quick Scan
        </Link>
      </div>
    </div>
  );
}
