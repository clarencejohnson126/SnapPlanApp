'use client'

import { useState, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { DropZone, DropZoneFile } from '@/components/features/DropZone'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Select } from '@/components/ui/Input'

type DocumentType = 'floor_plan' | 'door_schedule' | 'elevation' | 'auto'
type ExtractionOption = 'doors' | 'flooring' | 'drywall' | 'windows'

interface ExtractionConfig {
  documentType: DocumentType
  scale: string
  wallHeight: string
  autoDetectScale: boolean
  extractOptions: ExtractionOption[]
}

const SCALE_OPTIONS = [
  { value: '1:50', label: '1:50' },
  { value: '1:100', label: '1:100' },
  { value: '1:200', label: '1:200' },
  { value: '1:250', label: '1:250' },
  { value: '1:500', label: '1:500' },
  { value: 'auto', label: 'Auto-detect' },
]

export default function UploadPage() {
  const t = useTranslations()
  const router = useRouter()

  const [file, setFile] = useState<DropZoneFile | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [config, setConfig] = useState<ExtractionConfig>({
    documentType: 'auto',
    scale: 'auto',
    wallHeight: '2.6',
    autoDetectScale: true,
    extractOptions: ['doors', 'flooring', 'drywall'],
  })

  const handleFilesSelected = useCallback((files: DropZoneFile[]) => {
    if (files.length > 0) {
      setFile(files[0])
      setError(null)
    }
  }, [])

  const toggleExtractionOption = useCallback((option: ExtractionOption) => {
    setConfig(prev => ({
      ...prev,
      extractOptions: prev.extractOptions.includes(option)
        ? prev.extractOptions.filter(o => o !== option)
        : [...prev.extractOptions, option]
    }))
  }, [])

  const handleStartAnalysis = useCallback(async () => {
    if (!file) return

    setIsUploading(true)
    setError(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_SNAPGRID_API_URL || 'http://localhost:8000'

      // Collect results from all selected extraction options
      const results: Record<string, unknown> = {}
      const errors: string[] = []

      // For door schedules, use the schedule extraction endpoint
      if (config.documentType === 'door_schedule') {
        const formData = new FormData()
        formData.append('file', file.file)

        const response = await fetch(`${apiUrl}/api/v1/gewerke/doors/from-schedule`, {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || 'Upload failed')
        }

        results.doors = await response.json()
      } else {
        // For floor plans, call the appropriate endpoints based on extract options
        const scale = config.scale === 'auto' ? 100 : parseInt(config.scale.split(':')[1] || '100')

        // Extract doors if selected
        if (config.extractOptions.includes('doors')) {
          const formData = new FormData()
          formData.append('file', file.file)

          const response = await fetch(
            `${apiUrl}/api/v1/gewerke/doors/from-plan?scale=${scale}&use_yolo=true&use_vector=true`,
            { method: 'POST', body: formData }
          )

          if (response.ok) {
            results.doors = await response.json()
          } else {
            errors.push('Door detection failed')
          }
        }

        // Extract flooring/rooms if selected
        if (config.extractOptions.includes('flooring')) {
          const formData = new FormData()
          formData.append('file', file.file)

          const response = await fetch(
            `${apiUrl}/api/v1/gewerke/flooring/from-plan`,
            { method: 'POST', body: formData }
          )

          if (response.ok) {
            results.flooring = await response.json()
          } else {
            errors.push('Room extraction failed')
          }
        }

        // Extract drywall if selected
        if (config.extractOptions.includes('drywall')) {
          const formData = new FormData()
          formData.append('file', file.file)

          const response = await fetch(
            `${apiUrl}/api/v1/gewerke/drywall/from-plan?scale=${scale}&wall_height_m=${config.wallHeight}`,
            { method: 'POST', body: formData }
          )

          if (response.ok) {
            results.drywall = await response.json()
          } else {
            errors.push('Drywall calculation failed')
          }
        }
      }

      // Check if we got any results
      if (Object.keys(results).length === 0) {
        throw new Error('No data could be extracted from this document')
      }

      // Store results in sessionStorage and navigate to results page
      sessionStorage.setItem('analysisResult', JSON.stringify(results))
      sessionStorage.setItem('fileName', file.file.name)

      router.push('/results/latest')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
        setError('Could not connect to the backend API. Make sure the backend server is running on port 8000.')
      } else {
        setError(errorMessage)
      }
    } finally {
      setIsUploading(false)
    }
  }, [file, config, router])

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors mb-4"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          {t('common.back')}
        </button>
        <h1 className="text-2xl font-bold text-text-primary">{t('upload.title')}</h1>
        <p className="text-text-secondary mt-1">{t('upload.subtitle')}</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Left Column - File Upload */}
        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            {t('upload.step1')}
          </h2>
          <DropZone
            onFilesSelected={handleFilesSelected}
            accept=".pdf"
            labels={{
              title: t('upload.dropzoneTitle'),
              subtitle: t('upload.dropzoneSubtitle'),
              dragActive: t('upload.dropzoneDrag'),
              fileSelected: t('upload.fileReady'),
              browse: t('upload.browse'),
            }}
          />
        </div>

        {/* Right Column - Configuration */}
        <div>
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            {t('upload.step2')}
          </h2>

          <Card padding="lg" className="space-y-6">
            {/* Document Type */}
            <Select
              label={t('upload.documentType')}
              value={config.documentType}
              onChange={(e) => setConfig(prev => ({ ...prev, documentType: e.target.value as DocumentType }))}
              options={[
                { value: 'auto', label: t('upload.docTypeAuto') },
                { value: 'floor_plan', label: t('upload.docTypeFloorPlan') },
                { value: 'door_schedule', label: t('upload.docTypeDoorSchedule') },
                { value: 'elevation', label: t('upload.docTypeElevation') },
              ]}
            />

            {/* Scale */}
            <Select
              label={t('upload.scale')}
              value={config.scale}
              onChange={(e) => setConfig(prev => ({ ...prev, scale: e.target.value }))}
              options={SCALE_OPTIONS}
            />

            {/* Wall Height */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                {t('upload.wallHeight')}
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.1"
                  min="2.0"
                  max="5.0"
                  value={config.wallHeight}
                  onChange={(e) => setConfig(prev => ({ ...prev, wallHeight: e.target.value }))}
                  className="w-24 px-3 py-2 bg-bg-secondary border border-border rounded-lg text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-blue"
                />
                <span className="text-text-secondary">m</span>
              </div>
            </div>

            {/* Extraction Options */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-3">
                {t('upload.extractOptions')}
              </label>
              <div className="grid grid-cols-2 gap-3">
                {(['doors', 'flooring', 'drywall', 'windows'] as ExtractionOption[]).map((option) => (
                  <button
                    key={option}
                    onClick={() => toggleExtractionOption(option)}
                    className={`
                      px-4 py-3 rounded-lg border text-left transition-all duration-200
                      ${config.extractOptions.includes(option)
                        ? 'border-accent-blue bg-accent-blue/10 text-text-primary'
                        : 'border-border bg-bg-secondary text-text-secondary hover:border-text-muted'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-lg">
                        {option === 'doors' && '🚪'}
                        {option === 'flooring' && '📐'}
                        {option === 'drywall' && '🧱'}
                        {option === 'windows' && '🪟'}
                      </span>
                      <span className="font-medium">{t(`upload.option_${option}`)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Action Button */}
      <div className="mt-8 flex justify-end">
        <Button
          size="lg"
          disabled={!file || isUploading || config.extractOptions.length === 0}
          isLoading={isUploading}
          onClick={handleStartAnalysis}
        >
          {isUploading ? t('processing.analyzing') : t('upload.startAnalysis')}
        </Button>
      </div>
    </div>
  )
}
