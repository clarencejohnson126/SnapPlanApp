"use client";

import { useState, useRef, useEffect } from "react";
import { clsx } from "clsx";

interface UserMenuProps {
  email?: string;
  onLogout: () => void;
  isLoggingOut?: boolean;
}

export function UserMenu({ email, onLogout, isLoggingOut }: UserMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Get initials from email
  const initials = email
    ? email
        .split("@")[0]
        .split(/[._-]/)
        .map((part) => part[0]?.toUpperCase())
        .slice(0, 2)
        .join("")
    : "?";

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "w-9 h-9 rounded-full flex items-center justify-center text-sm font-medium transition-colors",
          "bg-[#243B53] text-white hover:bg-[#2D4A66]"
        )}
      >
        {initials}
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-64 bg-[#1A2942] rounded-lg shadow-xl border border-white/10 overflow-hidden z-50">
          {/* User Info */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-[#243B53] flex items-center justify-center text-sm font-medium text-white">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {email?.split("@")[0] || "User"}
                </p>
                <p className="text-xs text-white/60 truncate">{email || "No email"}</p>
              </div>
            </div>
          </div>

          {/* Menu Items */}
          <div className="p-2">
            <button
              onClick={() => {
                setIsOpen(false);
                // Navigate to settings
                window.location.href = "/app/settings";
              }}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-white/80 hover:bg-white/5 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Account Settings
            </button>

            <button
              onClick={() => {
                setIsOpen(false);
                onLogout();
              }}
              disabled={isLoggingOut}
              className={clsx(
                "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isLoggingOut
                  ? "text-white/40 cursor-not-allowed"
                  : "text-red-400 hover:bg-red-500/10"
              )}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              {isLoggingOut ? "Signing out..." : "Sign Out"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
