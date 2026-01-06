"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { clsx } from "clsx";

interface ProjectSelectorProps {
  currentProjectId?: string;
  currentProjectName?: string;
}

export function ProjectSelector({
  currentProjectId,
  currentProjectName,
}: ProjectSelectorProps) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
          "bg-[#1A2942] hover:bg-[#243B53] text-white"
        )}
      >
        <svg className="w-4 h-4 text-[#00D4AA]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
        <span className="max-w-[200px] truncate">
          {currentProjectName || "Quick Scan"}
        </span>
        <svg
          className={clsx("w-4 h-4 transition-transform", isOpen && "rotate-180")}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-72 bg-[#1A2942] rounded-lg shadow-xl border border-white/10 overflow-hidden z-50">
          <div className="p-4 text-center text-white/60 text-sm">
            Project management coming soon.<br />
            Use Quick Scan for instant analysis.
          </div>
          <div className="p-2 border-t border-white/5">
            <button
              onClick={() => {
                setIsOpen(false);
                router.push("/app/scan");
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-[#00D4AA] hover:bg-[#00D4AA]/10 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Go to Quick Scan
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
