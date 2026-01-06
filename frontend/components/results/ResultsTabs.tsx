"use client";

import { clsx } from "clsx";

interface Tab {
  id: string;
  label: string;
  disabled?: boolean;
  comingSoon?: boolean;
}

interface ResultsTabsProps {
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

const tabs: Tab[] = [
  { id: "areas", label: "Areas" },
  { id: "doors", label: "Doors", disabled: true, comingSoon: true },
  { id: "windows", label: "Windows", disabled: true, comingSoon: true },
  { id: "drywall", label: "Drywall", disabled: true, comingSoon: true },
  { id: "flooring", label: "Flooring", disabled: true, comingSoon: true },
];

export function ResultsTabs({ activeTab, onTabChange }: ResultsTabsProps) {
  return (
    <div className="flex items-center gap-1 bg-[#1A2942] rounded-lg p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => !tab.disabled && onTabChange(tab.id)}
          disabled={tab.disabled}
          className={clsx(
            "px-4 py-2 rounded-md text-sm font-medium transition-colors relative",
            activeTab === tab.id
              ? "bg-[#00D4AA] text-[#0F1B2A]"
              : tab.disabled
                ? "text-[#64748B] cursor-not-allowed"
                : "text-[#94A3B8] hover:text-white hover:bg-white/5"
          )}
        >
          {tab.label}
          {tab.comingSoon && (
            <span className="ml-1.5 text-[10px] text-[#64748B]">(Soon)</span>
          )}
        </button>
      ))}
    </div>
  );
}
