"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { LanguageToggle } from "./LanguageToggle";
import { UserMenu } from "./UserMenu";
import { ProjectSelector } from "./ProjectSelector";

interface TopbarProps {
  userEmail?: string;
  projectName?: string;
  projectId?: string;
}

export function Topbar({ userEmail, projectName, projectId }: TopbarProps) {
  const router = useRouter();
  const supabase = createClient();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await supabase.auth.signOut();
      router.push("/");
      router.refresh();
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="sticky top-0 h-16 bg-[#0F1B2A] border-b border-white/5 flex items-center justify-between px-6 z-30">
      {/* Left: Project Selector */}
      <div className="flex items-center gap-4">
        {projectId ? (
          <ProjectSelector currentProjectId={projectId} currentProjectName={projectName} />
        ) : (
          <div className="text-white/60 text-sm">
            Select a project to get started
          </div>
        )}
      </div>

      {/* Right: Language Toggle + User Menu */}
      <div className="flex items-center gap-4">
        <LanguageToggle />
        <UserMenu
          email={userEmail}
          onLogout={handleLogout}
          isLoggingOut={isLoggingOut}
        />
      </div>
    </header>
  );
}
