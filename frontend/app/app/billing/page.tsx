import Link from "next/link";

export default function BillingPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Billing</h1>
        <p className="text-[#94A3B8] mt-1">
          Manage your subscription and payment methods
        </p>
      </div>

      {/* Coming soon card */}
      <div className="bg-[#1A2942] rounded-xl border border-white/5 p-12 text-center">
        <div className="w-16 h-16 rounded-full bg-[#00D4AA]/10 flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-[#00D4AA]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white mb-2">
          Billing Coming Soon
        </h2>
        <p className="text-[#94A3B8] max-w-md mx-auto mb-8">
          We&apos;re working on integrating Stripe for seamless subscription
          management. Stay tuned!
        </p>

        {/* Placeholder pricing cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
          <div className="bg-[#0F1B2A] rounded-lg border border-white/5 p-6">
            <h3 className="font-semibold text-white mb-1">Starter</h3>
            <p className="text-2xl font-bold text-white mb-2">
              Free
              <span className="text-sm text-[#64748B] font-normal">/month</span>
            </p>
            <ul className="text-sm text-[#94A3B8] space-y-1 text-left">
              <li>5 analyses/month</li>
              <li>1 project</li>
              <li>JSON export</li>
            </ul>
          </div>

          <div className="bg-[#0F1B2A] rounded-lg border border-[#00D4AA]/30 p-6 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <span className="px-3 py-1 rounded-full bg-[#00D4AA] text-[#0F1B2A] text-xs font-semibold">
                Popular
              </span>
            </div>
            <h3 className="font-semibold text-white mb-1">Pro</h3>
            <p className="text-2xl font-bold text-[#00D4AA] mb-2">
              €49
              <span className="text-sm text-[#64748B] font-normal">/month</span>
            </p>
            <ul className="text-sm text-[#94A3B8] space-y-1 text-left">
              <li>100 analyses/month</li>
              <li>Unlimited projects</li>
              <li>All export formats</li>
            </ul>
          </div>

          <div className="bg-[#0F1B2A] rounded-lg border border-white/5 p-6">
            <h3 className="font-semibold text-white mb-1">Enterprise</h3>
            <p className="text-2xl font-bold text-white mb-2">Custom</p>
            <ul className="text-sm text-[#94A3B8] space-y-1 text-left">
              <li>Unlimited analyses</li>
              <li>API access</li>
              <li>Priority support</li>
            </ul>
          </div>
        </div>

        <Link
          href="/app"
          className="inline-flex items-center gap-2 mt-8 text-sm text-[#00D4AA] hover:underline"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          Back to Dashboard
        </Link>
      </div>

      {/* TODO placeholder */}
      <div className="bg-[#1A2942]/50 rounded-lg border border-dashed border-white/10 p-4">
        <p className="text-xs text-[#64748B] font-mono">
          {/* TODO Phase 2: Stripe - Subscription management */}
          Stripe integration placeholder. Database tables ready: stripe_customers,
          subscriptions
        </p>
      </div>
    </div>
  );
}
