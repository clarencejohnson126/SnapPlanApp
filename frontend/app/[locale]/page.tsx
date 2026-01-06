'use client'

import { useState, useCallback, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface Project {
  id: string
  name: string
  rooms?: number
  area?: number
  updatedAt: string
}

export default function DashboardPage() {
  const t = useTranslations()
  const router = useRouter()
  const [isDragging, setIsDragging] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])

  // Load projects from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('snapplan_projects')
    if (stored) {
      try {
        setProjects(JSON.parse(stored))
      } catch (e) {
        console.error('Failed to parse projects:', e)
      }
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile && droppedFile.type === 'application/pdf') {
      router.push('/upload')
    }
  }, [router])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile && selectedFile.type === 'application/pdf') {
      router.push('/upload')
    }
  }, [router])

  return (
    <div className="min-h-screen bg-bg-primary flex flex-col">
      {/* Main Content - Centered Upload Area */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-32">
        {/* Logo/Title */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-white mb-2">SnapPlan</h1>
          <p className="text-blue-300/60 text-lg">
            {t('common.tagline') || 'Extract measurements from blueprints'}
          </p>
        </div>

        {/* Central Upload Area - Google/ChatGPT style */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`
            relative w-full max-w-2xl rounded-2xl transition-all cursor-pointer
            border-2 border-dashed
            ${isDragging
              ? 'border-accent-teal bg-accent-teal/10 scale-[1.02]'
              : 'border-white/20 bg-bg-card/30 hover:border-white/40 hover:bg-bg-card/50'
            }
          `}
        >
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <div className="flex flex-col items-center gap-4 py-12 px-8">
            <div className={`
              w-16 h-16 rounded-full flex items-center justify-center transition-colors
              ${isDragging ? 'bg-accent-teal/30' : 'bg-accent-teal/20'}
            `}>
              <svg className="w-8 h-8 text-accent-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div className="text-center">
              <p className="font-medium text-white text-lg">
                {isDragging ? t('upload.dropzoneDrag') || 'Drop to upload' : t('upload.dropzoneTitle') || 'Drop PDF here or click to upload'}
              </p>
              <p className="text-sm text-blue-300/50 mt-2">
                {t('upload.dropzoneSubtitle') || 'Supports floor plans and door schedules'}
              </p>
            </div>
          </div>
        </div>

        {/* Quick action hint */}
        <p className="text-blue-300/40 text-sm mt-6">
          {t('upload.hint') || 'PDF files up to 50MB'}
        </p>
      </div>

      {/* Recent Projects - Only show if there are any */}
      {projects.length > 0 && (
        <div className="px-6 pb-24">
          <div className="max-w-2xl mx-auto">
            <h3 className="text-sm font-semibold text-blue-300/50 uppercase tracking-wider mb-3">
              {t('dashboard.recentProjects') || 'Recent'}
            </h3>
            <div className="space-y-2">
              {projects.slice(0, 3).map((project) => (
                <Link
                  key={project.id}
                  href={`/results/${project.id}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-bg-card/50 border border-white/5 hover:border-white/10 hover:bg-bg-card transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-bg-secondary flex items-center justify-center">
                      <svg className="w-4 h-4 text-blue-300/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-medium text-white text-sm">{project.name}</p>
                      <p className="text-xs text-blue-300/40">
                        {project.area ? `${project.area.toLocaleString('de-DE')} m²` : ''}
                        {project.rooms && project.area ? ' · ' : ''}
                        {project.rooms ? `${project.rooms} rooms` : ''}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-blue-300/30">{project.updatedAt}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
