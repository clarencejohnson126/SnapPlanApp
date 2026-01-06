"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Project } from "@/lib/supabase/types";
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
  const supabase = createClient();
  const [isOpen, setIsOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch projects when dropdown opens
  useEffect(() => {
    if (isOpen) {
      fetchProjects();
    }
  }, [isOpen]);

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

  const fetchProjects = async () => {
    setIsLoading(true);
    try {
      const { data, error } = await supabase
        .from("projects")
        .select("*")
        .order("updated_at", { ascending: false })
        .limit(10);

      if (error) throw error;
      setProjects(data || []);
    } catch (error) {
      console.error("Failed to fetch projects:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectProject = (project: Project) => {
    setIsOpen(false);
    router.push(`/app/projects/${project.id}`);
  };

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
          {currentProjectName || "Select Project"}
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
          {/* New Project Button */}
          <div className="p-2 border-b border-white/5">
            <button
              onClick={() => {
                setIsOpen(false);
                router.push("/app/projects?new=true");
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-[#00D4AA] hover:bg-[#00D4AA]/10 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Project
            </button>
          </div>

          {/* Project List */}
          <div className="max-h-64 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center text-white/60 text-sm">
                Loading...
              </div>
            ) : projects.length === 0 ? (
              <div className="p-4 text-center text-white/60 text-sm">
                No projects yet
              </div>
            ) : (
              <ul className="p-2">
                {projects.map((project) => (
                  <li key={project.id}>
                    <button
                      onClick={() => handleSelectProject(project)}
                      className={clsx(
                        "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                        project.id === currentProjectId
                          ? "bg-[#00D4AA]/10 text-[#00D4AA]"
                          : "text-white hover:bg-white/5"
                      )}
                    >
                      <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                      <span className="truncate">{project.name}</span>
                      {project.id === currentProjectId && (
                        <svg className="w-4 h-4 ml-auto flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* View All Projects */}
          <div className="p-2 border-t border-white/5">
            <button
              onClick={() => {
                setIsOpen(false);
                router.push("/app/projects");
              }}
              className="w-full px-3 py-2 text-sm text-white/60 hover:text-white transition-colors"
            >
              View all projects
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
