"use client";

import { useState } from "react";
import { clsx } from "clsx";

type Language = "de" | "en";

export function LanguageToggle() {
  // In a real implementation, this would be connected to next-intl
  // For now, we'll use localStorage to persist the preference
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("language") as Language) || "de";
    }
    return "de";
  });

  const handleToggle = (lang: Language) => {
    setLanguage(lang);
    if (typeof window !== "undefined") {
      localStorage.setItem("language", lang);
      // In a real implementation, this would update the locale
      // For now, just refresh to apply (would use next-intl router)
    }
  };

  return (
    <div className="flex items-center bg-[#1A2942] rounded-lg p-0.5">
      <button
        onClick={() => handleToggle("de")}
        className={clsx(
          "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
          language === "de"
            ? "bg-[#00D4AA] text-[#0F1B2A]"
            : "text-white/60 hover:text-white"
        )}
      >
        DE
      </button>
      <button
        onClick={() => handleToggle("en")}
        className={clsx(
          "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
          language === "en"
            ? "bg-[#00D4AA] text-[#0F1B2A]"
            : "text-white/60 hover:text-white"
        )}
      >
        EN
      </button>
    </div>
  );
}
