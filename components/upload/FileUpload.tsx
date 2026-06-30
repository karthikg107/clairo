'use client'

import { useCallback, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils/cn'

// ── Types ────────────────────────────────────────────────────────────────────

const ACCEPTED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/jpeg',
  'image/png',
  'image/heic',
  'image/heif',
] as const

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.jpg', '.jpeg', '.png', '.heic']
const MAX_FILE_BYTES = 25 * 1024 * 1024 // 25 MB

type UploadMode = 'idle' | 'dragover' | 'selected' | 'error'

interface FileValidation {
  valid: boolean
  error?: string
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function validateFile(file: File): FileValidation {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  const typeOk =
    (ACCEPTED_MIME_TYPES as readonly string[]).includes(file.type) ||
    ACCEPTED_EXTENSIONS.includes(ext)

  if (!typeOk) {
    return { valid: false, error: 'upload.error.type' }
  }
  if (file.size > MAX_FILE_BYTES) {
    return { valid: false, error: 'upload.error.size' }
  }
  return { valid: true }
}

// ── Component ─────────────────────────────────────────────────────────────────

interface FileUploadProps {
  onFileSelected: (file: File) => void
  onCameraOpen: () => void
  disabled?: boolean
}

export function FileUpload({ onFileSelected, onCameraOpen, disabled = false }: FileUploadProps) {
  const t = useTranslations()
  const [mode, setMode] = useState<UploadMode>('idle')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const galleryInputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    (file: File) => {
      const validation = validateFile(file)
      if (!validation.valid) {
        setMode('error')
        setErrorKey(validation.error ?? 'upload.error.generic')
        setSelectedFile(null)
        return
      }
      setSelectedFile(file)
      setMode('selected')
      setErrorKey(null)
      onFileSelected(file)
    },
    [onFileSelected],
  )

  // Drag-and-drop handlers
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) setMode('dragover')
  }
  const onDragLeave = () => setMode('idle')
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (disabled) return
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    // Reset so same file can be re-selected
    e.target.value = ''
  }

  const isDragover = mode === 'dragover'
  const isError = mode === 'error'
  const isSelected = mode === 'selected'

  return (
    <div className="w-full max-w-sm mx-auto flex flex-col gap-4">
      {/* ── Legal disclaimer (non-negotiable, always visible) ─────────────── */}
      <div
        role="note"
        className="legal-disclaimer text-xs leading-relaxed"
        aria-label={t('disclaimer.label')}
      >
        {t('disclaimer.upload')}
      </div>

      {/* ── Drop zone ────────────────────────────────────────────────────── */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={t('upload.dropzone_label')}
        aria-describedby="upload-hint"
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
            fileInputRef.current?.click()
          }
        }}
        className={cn(
          'relative flex flex-col items-center justify-center gap-3',
          'rounded-card border-2 border-dashed p-8 text-center',
          'transition-colors duration-150 cursor-pointer',
          'focus-visible:outline-2 focus-visible:outline-brand-500 focus-visible:outline-offset-2',
          isDragover && 'border-brand-500 bg-brand-50',
          isError && 'border-danger-500 bg-danger-50',
          isSelected && 'border-success-500 bg-success-50',
          !isDragover && !isError && !isSelected && 'border-gray-300 bg-white hover:border-brand-400 hover:bg-brand-50/50',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        {/* Icon */}
        <div
          className={cn(
            'flex h-12 w-12 items-center justify-center rounded-full',
            isSelected ? 'bg-success-100' : isError ? 'bg-danger-100' : 'bg-brand-100',
          )}
          aria-hidden="true"
        >
          {isSelected ? (
            <svg className="h-6 w-6 text-success-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          ) : isError ? (
            <svg className="h-6 w-6 text-danger-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          ) : (
            <svg className="h-6 w-6 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          )}
        </div>

        {/* Text */}
        {isSelected && selectedFile ? (
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium text-dark-text truncate max-w-[200px]">
              {selectedFile.name}
            </p>
            <p className="text-xs text-gray-500">{formatBytes(selectedFile.size)}</p>
          </div>
        ) : (
          <>
            <p className="text-sm font-medium text-dark-text">
              {isDragover ? t('upload.drop_now') : t('upload.drag_or_tap')}
            </p>
            <p id="upload-hint" className="text-xs text-gray-500">
              {t('upload.accepted_types')}
            </p>
          </>
        )}

        {/* Error message */}
        {isError && errorKey && (
          <p role="alert" className="text-xs font-medium text-danger-500 mt-1">
            {t(errorKey)}
          </p>
        )}

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="sr-only"
          aria-hidden="true"
          onChange={onInputChange}
          disabled={disabled}
        />
      </div>

      {/* ── Mobile upload options ─────────────────────────────────────────── */}
      <div className="flex flex-col gap-2" role="group" aria-label={t('upload.options_label')}>
        {/* Take photo (custom camera) */}
        <button
          type="button"
          onClick={onCameraOpen}
          disabled={disabled}
          className={cn(
            'flex items-center gap-3 w-full rounded-card border border-gray-200',
            'bg-white px-4 py-3 text-left text-sm font-medium text-dark-text',
            'min-h-touch transition-colors',
            'hover:border-brand-400 hover:bg-brand-50',
            'focus-visible:outline-2 focus-visible:outline-brand-500 focus-visible:outline-offset-2',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
          aria-label={t('upload.camera_label')}
        >
          <span aria-hidden="true" className="text-brand-500 flex-shrink-0">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </span>
          {t('upload.take_photo')}
        </button>

        {/* Upload from gallery */}
        <button
          type="button"
          onClick={() => !disabled && galleryInputRef.current?.click()}
          disabled={disabled}
          className={cn(
            'flex items-center gap-3 w-full rounded-card border border-gray-200',
            'bg-white px-4 py-3 text-left text-sm font-medium text-dark-text',
            'min-h-touch transition-colors',
            'hover:border-brand-400 hover:bg-brand-50',
            'focus-visible:outline-2 focus-visible:outline-brand-500 focus-visible:outline-offset-2',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
          aria-label={t('upload.gallery_label')}
        >
          <span aria-hidden="true" className="text-brand-500 flex-shrink-0">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </span>
          {t('upload.from_gallery')}
          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*"
            capture={undefined}
            className="sr-only"
            aria-hidden="true"
            onChange={onInputChange}
            disabled={disabled}
          />
        </button>
      </div>

      {/* ── Privacy reminder (must be visible without scroll on 375px) ──────── */}
      <p className="text-xs text-gray-500 text-center leading-relaxed">
        🔒 {t('upload.privacy_reminder')}
      </p>
    </div>
  )
}
