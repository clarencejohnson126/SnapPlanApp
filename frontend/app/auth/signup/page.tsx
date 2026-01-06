"use client";

import { useState } from "react";
import Link from "next/link";
import { signup } from "../actions";

export default function SignupPage() {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(formData: FormData) {
    setIsLoading(true);
    setError(null);

    const result = await signup(formData);

    if (result?.error) {
      setError(result.error);
      setIsLoading(false);
    }
  }

  return (
    <div className="bg-[#1A2942] rounded-xl shadow-xl border border-white/10 p-8">
      {/* Logo */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-[#00D4AA]/10 mb-4">
          <svg
            className="w-6 h-6 text-[#00D4AA]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-white">Create Account</h1>
        <p className="text-[#94A3B8] mt-2">Get started with SnapPlan</p>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Form */}
      <form action={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-medium text-[#94A3B8] mb-2"
          >
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            className="w-full px-4 py-3 rounded-lg bg-[#0F1B2A] border border-white/10 text-white placeholder:text-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#00D4AA]/50 focus:border-[#00D4AA] transition-colors"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="block text-sm font-medium text-[#94A3B8] mb-2"
          >
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="new-password"
            minLength={6}
            className="w-full px-4 py-3 rounded-lg bg-[#0F1B2A] border border-white/10 text-white placeholder:text-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#00D4AA]/50 focus:border-[#00D4AA] transition-colors"
            placeholder="At least 6 characters"
          />
        </div>

        <div>
          <label
            htmlFor="confirmPassword"
            className="block text-sm font-medium text-[#94A3B8] mb-2"
          >
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            name="confirmPassword"
            type="password"
            required
            autoComplete="new-password"
            minLength={6}
            className="w-full px-4 py-3 rounded-lg bg-[#0F1B2A] border border-white/10 text-white placeholder:text-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#00D4AA]/50 focus:border-[#00D4AA] transition-colors"
            placeholder="Confirm your password"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-3 px-4 rounded-lg bg-[#00D4AA] text-[#0F1B2A] font-semibold hover:bg-[#00D4AA]/90 focus:outline-none focus:ring-2 focus:ring-[#00D4AA]/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? "Creating account..." : "Create Account"}
        </button>
      </form>

      {/* Terms */}
      <p className="mt-4 text-xs text-[#64748B] text-center">
        By creating an account, you agree to our Terms of Service and Privacy
        Policy
      </p>

      {/* Login link */}
      <div className="mt-6 text-center">
        <p className="text-[#94A3B8]">
          Already have an account?{" "}
          <Link
            href="/auth/login"
            className="text-[#00D4AA] hover:underline font-medium"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
