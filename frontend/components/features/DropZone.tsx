'use client'

import { useState, useCallback, useRef } from 'react'
import { clsx } from 'clsx'

export interface DropZoneFile {
  file: File
  preview?: string
}

export interface DropZoneProps {
  onFilesSelected: (files: DropZoneFile[]) => void
  accept?: string
  multiple?: boolean
  maxSize?: number // in bytes
  disabled?: boolean
  className?: string
  labels?: {
    title?: string
    subtitle?: string
    dragActive?: string
    fileSelected?: string
    browse?: string
  }
}

export function DropZone({
  onFilesSelected,
  accept = '.pdf',
  multiple = false,
  maxSize = 50 * 1024 * 1024, // 50MB default
  disabled = false,
  className,
  labels = {},
}: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<DropZoneFile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const {
    title = 'Drop PDF here or click to upload',
    subtitle = 'Supports: Floor Plans, Door Schedules',
    dragActive = 'Drop file here...',
    fileSelected = 'File ready for upload',
    browse = 'Browse files',
  } = labels

  const validateFile = useCallback((file: File): string | null => {
    // Check file type
    const acceptedTypes = accept.split(',').map(t => t.trim())
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
    const mimeMatch = acceptedTypes.some(type => {
      if (type.startsWith('.')) {
        return fileExtension === type.toLowerCase()
      }
      return file.type.includes(type.replace('*', ''))
    })

    if (!mimeMatch) {
      return `Invalid file type. Accepted: ${accept}`
    }

    // Check file size
    if (file.size > maxSize) {
      const maxMB = (maxSize / 1024 / 1024).toFixed(0)
      return `File too large. Maximum size: ${maxMB}MB`
    }

    return null
  }, [accept, maxSize])

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return

    const file = files[0]
    const validationError = validateFile(file)

    if (validationError) {
      setError(validationError)
      setSelectedFile(null)
      return
    }

    setError(null)
    const dropZoneFile: DropZoneFile = { file }

    // Create preview for PDFs (just show file info, not actual preview)
    setSelectedFile(dropZoneFile)
    onFilesSelected([dropZoneFile])
  }, [validateFile, onFilesSelected])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) {
      setIsDragging(true)
    }
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    if (disabled) return

    handleFiles(e.dataTransfer.files)
  }, [disabled, handleFiles])

  const handleClick = useCallback(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.click()
    }
  }, [disabled])

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files)
  }, [handleFiles])

  const handleRemoveFile = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedFile(null)
    setError(null)
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }, [])

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(2) + ' MB'
  }

  return (
    <div className={clsx('w-full', className)}>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={clsx(
          'relative border-2 border-dashed rounded-xl p-8 sm:p-12 text-center transition-all duration-200 cursor-pointer',
          disabled && 'opacity-50 cursor-not-allowed',
          isDragging && 'border-accent-blue bg-accent-blue/10',
          selectedFile && !isDragging && 'border-green-500 bg-green-500/10',
          !isDragging && !selectedFile && 'border-border bg-bg-card hover:border-text-muted'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileInputChange}
          className="hidden"
          disabled={disabled}
        />

        <div className="flex flex-col items-center gap-4">
          {selectedFile ? (
            // File selected state
            <>
              <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-lg font-medium text-text-primary">{selectedFile.file.name}</p>
                <p className="text-sm text-text-secondary mt-1">
                  {formatFileSize(selectedFile.file.size)}
                </p>
                <p className="text-sm text-green-400 mt-1">{fileSelected}</p>
              </div>
              <button
                onClick={handleRemoveFile}
                className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary border border-border rounded-lg hover:bg-bg-hover transition-colors"
              >
                Remove file
              </button>
            </>
          ) : isDragging ? (
            // Dragging state
            <>
              <div className="w-16 h-16 bg-accent-blue/20 rounded-full flex items-center justify-center animate-pulse">
                <svg className="w-8 h-8 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
              </div>
              <p className="text-lg font-medium text-accent-blue">{dragActive}</p>
            </>
          ) : (
            // Default state
            <>
              <div className="w-16 h-16 bg-bg-hover rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-lg font-medium text-text-primary">{title}</p>
                <p className="text-sm text-text-secondary mt-1">{subtitle}</p>
              </div>
              <span className="text-sm text-accent-blue hover:underline">{browse}</span>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  )
}
