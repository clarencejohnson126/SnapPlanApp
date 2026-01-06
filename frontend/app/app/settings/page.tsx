"use client";

import { useState } from "react";
import { clsx } from "clsx";
import Link from "next/link";

type Language = "de" | "en";

export default function SettingsPage() {
  // Language preference (would be connected to next-intl in production)
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("language") as Language) || "de";
    }
    return "de";
  });

  const handleLanguageChange = (lang: Language) => {
    setLanguage(lang);
    if (typeof window !== "undefined") {
      localStorage.setItem("language", lang);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-[#94A3B8] mt-1">
          Manage your account and preferences
        </p>
      </div>

      {/* Language settings */}
      <div className="bg-[#1A2942] rounded-xl border border-white/5 overflow-hidden">
        <div className="px-6 py-4 border-b border-white/5">
          <h2 className="font-semibold text-white">Language</h2>
          <p className="text-sm text-[#64748B] mt-1">
            Choose your preferred language for the interface
          </p>
        </div>
        <div className="p-6">
          <div className="flex gap-4">
            <button
              onClick={() => handleLanguageChange("de")}
              className={clsx(
                "flex-1 p-4 rounded-lg border transition-colors",
                language === "de"
                  ? "border-[#00D4AA] bg-[#00D4AA]/5"
                  : "border-white/10 hover:border-white/20"
              )}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">🇩🇪</span>
                <div className="text-left">
                  <p className="font-medium text-white">Deutsch</p>
                  <p className="text-sm text-[#64748B]">German</p>
                </div>
              </div>
            </button>
            <button
              onClick={() => handleLanguageChange("en")}
              className={clsx(
                "flex-1 p-4 rounded-lg border transition-colors",
                language === "en"
                  ? "border-[#00D4AA] bg-[#00D4AA]/5"
                  : "border-white/10 hover:border-white/20"
              )}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">🇬🇧</span>
                <div className="text-left">
                  <p className="font-medium text-white">English</p>
                  <p className="text-sm text-[#64748B]">English</p>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Account settings */}
      <div className="bg-[#1A2942] rounded-xl border border-white/5 overflow-hidden">
        <div className="px-6 py-4 border-b border-white/5">
          <h2 className="font-semibold text-white">Account</h2>
          <p className="text-sm text-[#64748B] mt-1">
            Manage your account settings
          </p>
        </div>
        <div className="divide-y divide-white/5">
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-white">Email notifications</p>
              <p className="text-sm text-[#64748B]">
                Receive email updates about your analyses
              </p>
            </div>
            <button
              className="relative w-11 h-6 rounded-full bg-[#0F1B2A] border border-white/10 transition-colors"
              aria-label="Toggle email notifications"
            >
              <span className="absolute left-1 top-1 w-4 h-4 rounded-full bg-[#64748B] transition-transform" />
            </button>
          </div>
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-white">Two-factor authentication</p>
              <p className="text-sm text-[#64748B]">
                Add an extra layer of security
              </p>
            </div>
            <span className="px-2 py-1 rounded bg-[#64748B]/20 text-[#64748B] text-xs">
              Coming Soon
            </span>
          </div>
        </div>
      </div>

      {/* Danger zone */}
      <div className="bg-[#1A2942] rounded-xl border border-red-500/20 overflow-hidden">
        <div className="px-6 py-4 border-b border-red-500/10">
          <h2 className="font-semibold text-red-400">Danger Zone</h2>
          <p className="text-sm text-[#64748B] mt-1">
            Irreversible and destructive actions
          </p>
        </div>
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-white">Delete account</p>
              <p className="text-sm text-[#64748B]">
                Permanently delete your account and all data
              </p>
            </div>
            <button
              className="px-4 py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors text-sm"
              disabled
            >
              Delete Account
            </button>
          </div>
        </div>
      </div>

      {/* Back link */}
      <Link
        href="/app"
        className="inline-flex items-center gap-2 text-sm text-[#00D4AA] hover:underline"
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
  );
}
