"use client";

import { useRouter } from "next/navigation";
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

  const handleLogout = async () => {
    router.push("/");
  };

  return (
    <header className="sticky top-0 h-16 bg-[#0F1B2A] border-b border-white/5 flex items-center justify-between px-6 z-30">
      {/* Left: Project Selector */}
      <div className="flex items-center gap-4">
        <ProjectSelector currentProjectId={projectId} currentProjectName={projectName} />
      </div>

      {/* Right: Language Toggle + User Menu */}
      <div className="flex items-center gap-4">
        <LanguageToggle />
        <UserMenu
          email={userEmail}
          onLogout={handleLogout}
          isLoggingOut={false}
        />
      </div>
    </header>
  );
}
