import Link from "next/link";

export default function NewProjectPage() {
  return (
    <div className="max-w-2xl mx-auto">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm">
          <li>
            <Link href="/app/projects" className="text-[#94A3B8] hover:text-white">
              Projects
            </Link>
          </li>
          <li className="text-[#64748B]">/</li>
          <li className="text-white">New Project</li>
        </ol>
      </nav>

      {/* Card */}
      <div className="bg-[#1A2942] rounded-xl border border-white/5 p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-[#F59E0B]/10 flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-[#F59E0B]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white mb-2">
          Feature Not Available in Demo
        </h2>
        <p className="text-[#94A3B8] max-w-md mx-auto mb-8">
          Project creation requires authentication. For now, use Quick Scan to test the extraction without saving.
        </p>

        <div className="flex items-center justify-center gap-4">
          <Link
            href="/app/projects"
            className="px-4 py-2.5 rounded-lg border border-white/10 text-[#94A3B8] hover:text-white hover:border-white/20 transition-colors"
          >
            Back
          </Link>
          <Link
            href="/app/scan"
            className="px-6 py-2.5 rounded-lg bg-[#00D4AA] text-[#0F1B2A] font-semibold hover:bg-[#00D4AA]/90 transition-colors"
          >
            Go to Quick Scan
          </Link>
        </div>
      </div>
    </div>
  );
}
