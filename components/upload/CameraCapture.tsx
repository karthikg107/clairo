'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils/cn'

// ── Quality scoring ───────────────────────────────────────────────────────────

interface QualityResult {
  score: number          // 0–100
  issues: QualityIssue[]
}

type QualityIssue =
  | 'too_dark'
  | 'too_bright'
  | 'blurry'
  | 'skewed'
  | 'too_far'
  | 'motion'

/**
 * Compute a simple quality score from an ImageData frame.
 * Real production: replace with a WASM Sobel edge detector.
 */
function computeQuality(imageData: ImageData): QualityResult {
  const { data, width, height } = imageData
  const issues: QualityIssue[] = []

  // Luminance average
  let totalLum = 0
  let edgeStrength = 0
  const step = 4 // sample every 4th pixel for speed

  for (let i = 0; i < data.length; i += 4 * step) {
    const r = data[i], g = data[i + 1], b = data[i + 2]
    totalLum += 0.299 * r + 0.587 * g + 0.114 * b
  }
  const avgLum = totalLum / (data.length / (4 * step))

  // Edge strength (simplified Laplacian on luminance channel)
  for (let y = 1; y < height - 1; y += step) {
    for (let x = 1; x < width - 1; x += step) {
      const idx = (y * width + x) * 4
      const c = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2]
      const l = 0.299 * data[idx - 4] + 0.587 * data[idx - 3] + 0.114 * data[idx - 2]
      const r2 = 0.299 * data[idx + 4] + 0.587 * data[idx + 5] + 0.114 * data[idx + 6]
      edgeStrength += Math.abs(2 * c - l - r2)
    }
  }
  const normalizedEdge = Math.min(100, edgeStrength / (width * height / (step * step)) * 0.5)

  // Score components
  let score = 0

  if (avgLum < 40) {
    issues.push('too_dark')
    score += 10
  } else if (avgLum > 220) {
    issues.push('too_bright')
    score += 20
  } else {
    // Lighting is good
    score += 40 * (1 - Math.abs(avgLum - 130) / 130)
  }

  // Edge sharpness contribution
  score += Math.min(60, normalizedEdge)

  return { score: Math.round(Math.max(0, Math.min(100, score))), issues }
}

function compressImage(canvas: HTMLCanvasElement, maxDim = 4000): Blob | null {
  let { width, height } = canvas
  if (width > maxDim || height > maxDim) {
    const ratio = Math.min(maxDim / width, maxDim / height)
    const compressed = document.createElement('canvas')
    compressed.width = Math.round(width * ratio)
    compressed.height = Math.round(height * ratio)
    compressed.getContext('2d')?.drawImage(canvas, 0, 0, compressed.width, compressed.height)
    return new Promise<Blob | null>((res) => compressed.toBlob(res, 'image/jpeg', 0.92)) as unknown as Blob
  }
  return new Promise<Blob | null>((res) => canvas.toBlob(res, 'image/jpeg', 0.92)) as unknown as Blob
}

// ── Component ─────────────────────────────────────────────────────────────────

interface CameraCaptureProps {
  onCapture: (file: File) => void
  onClose: () => void
}

type CameraState = 'requesting' | 'active' | 'countdown' | 'preview' | 'error'

export function CameraCapture({ onCapture, onClose }: CameraCaptureProps) {
  const t = useTranslations()
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animFrameRef = useRef<number>(0)
  const countdownTimerRef = useRef<NodeJS.Timeout | null>(null)

  const [state, setState] = useState<CameraState>('requesting')
  const [quality, setQuality] = useState<QualityResult>({ score: 0, issues: [] })
  const [torchOn, setTorchOn] = useState(false)
  const [torchSupported, setTorchSupported] = useState(false)
  const [countdown, setCountdown] = useState(3)
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null)
  const [lowQualityWarning, setLowQualityWarning] = useState(false)
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment')

  // Start camera
  const startCamera = useCallback(async (facing: 'environment' | 'user' = 'environment') => {
    setState('requesting')
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facing,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      // Check torch support
      const track = stream.getVideoTracks()[0]
      const caps = track.getCapabilities?.() as Record<string, unknown> | undefined
      setTorchSupported(!!caps?.torch)
      setState('active')
    } catch {
      setState('error')
    }
  }, [])

  useEffect(() => {
    startCamera(facingMode)
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      cancelAnimationFrame(animFrameRef.current)
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current)
    }
  }, [facingMode, startCamera])

  // Quality analysis loop
  useEffect(() => {
    if (state !== 'active') return
    const analyse = () => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState < 2) {
        animFrameRef.current = requestAnimationFrame(analyse)
        return
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      ctx.drawImage(video, 0, 0)
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
      const result = computeQuality(imageData)
      setQuality(result)

      // Auto-capture at 80%+
      if (result.score >= 80) {
        triggerAutoCapture(canvas)
      } else {
        animFrameRef.current = requestAnimationFrame(analyse)
      }
    }
    animFrameRef.current = requestAnimationFrame(analyse)
    return () => cancelAnimationFrame(animFrameRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  const triggerAutoCapture = useCallback(
    (canvas: HTMLCanvasElement) => {
      if (state !== 'active') return
      setState('countdown')
      let count = 3
      setCountdown(count)
      countdownTimerRef.current = setInterval(() => {
        count -= 1
        setCountdown(count)
        if (count <= 0) {
          if (countdownTimerRef.current) clearInterval(countdownTimerRef.current)
          captureFrame(canvas)
        }
      }, 1000)
    },
    [state], // eslint-disable-line react-hooks/exhaustive-deps
  )

  const captureFrame = useCallback(async (canvas?: HTMLCanvasElement) => {
    const c = canvas ?? canvasRef.current
    const video = videoRef.current
    if (!c || !video) return

    if (!canvas) {
      // Manual capture
      const ctx = c.getContext('2d')
      c.width = video.videoWidth
      c.height = video.videoHeight
      ctx?.drawImage(video, 0, 0)
    }

    const blob = await (compressImage(c) as unknown as Promise<Blob | null>)
    if (!blob) return

    streamRef.current?.getTracks().forEach((t) => t.stop())
    cancelAnimationFrame(animFrameRef.current)

    if (quality.score < 50) {
      setLowQualityWarning(true)
    }
    setCapturedBlob(blob)
    setState('preview')
  }, [quality.score])

  const toggleTorch = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks()[0]
    if (!track) return
    const newState = !torchOn
    await track.applyConstraints({ advanced: [{ torch: newState } as MediaTrackConstraintSet] })
    setTorchOn(newState)
  }, [torchOn])

  const confirmCapture = useCallback(() => {
    if (!capturedBlob) return
    const file = new File([capturedBlob], `clairo-capture-${Date.now()}.jpg`, { type: 'image/jpeg' })
    onCapture(file)
  }, [capturedBlob, onCapture])

  const retake = useCallback(() => {
    setCapturedBlob(null)
    setLowQualityWarning(false)
    setCountdown(3)
    startCamera(facingMode)
  }, [facingMode, startCamera])

  // ── Quality indicator ────────────────────────────────────────────────────

  const qualityColor =
    quality.score >= 80 ? '#1A7A4A' : quality.score >= 50 ? '#B36200' : '#B91C1C'

  const qualityLabel = (): string => {
    if (quality.issues.includes('too_dark')) return t('camera.issue.too_dark')
    if (quality.issues.includes('too_bright')) return t('camera.issue.too_bright')
    if (quality.issues.includes('blurry')) return t('camera.issue.blurry')
    if (quality.score >= 80) return t('camera.quality.good')
    if (quality.score >= 50) return t('camera.quality.ok')
    return t('camera.quality.poor')
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (state === 'error') {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90 p-8 text-center">
        <div className="rounded-full bg-danger-100 p-4 mb-4">
          <svg className="h-8 w-8 text-danger-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
        </div>
        <h2 className="text-white text-lg font-medium mb-2">{t('camera.error.permission')}</h2>
        <p className="text-white/70 text-sm mb-6">{t('camera.error.permission_hint')}</p>
        <button
          onClick={onClose}
          className="bg-white text-dark-text rounded-card px-6 py-3 text-sm font-medium min-h-touch"
        >
          {t('camera.fallback.use_gallery')}
        </button>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black">
      {/* Hidden canvas for quality analysis */}
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

      {/* Top bar */}
      <div className="flex items-center justify-between px-4 pt-safe-top pb-3 pt-4">
        <button
          onClick={onClose}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white"
          aria-label={t('common.close')}
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="flex items-center gap-2">
          {torchSupported && state === 'active' && (
            <button
              onClick={toggleTorch}
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-full',
                torchOn ? 'bg-warning-400 text-white' : 'bg-white/10 text-white',
              )}
              aria-label={torchOn ? t('camera.torch.off') : t('camera.torch.on')}
              aria-pressed={torchOn}
            >
              <svg className="h-5 w-5" fill={torchOn ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Viewfinder */}
      <div className="relative flex-1 overflow-hidden">
        {state === 'preview' && capturedBlob ? (
          <img
            src={URL.createObjectURL(capturedBlob)}
            alt={t('camera.preview.alt')}
            className="h-full w-full object-cover"
          />
        ) : (
          <video
            ref={videoRef}
            playsInline
            muted
            className="h-full w-full object-cover"
            aria-label={t('camera.viewfinder_label')}
          />
        )}

        {/* Corner guides (green when quality ≥ 80) */}
        {(state === 'active' || state === 'countdown') && (
          <div className="pointer-events-none absolute inset-6" aria-hidden="true">
            {(['tl', 'tr', 'bl', 'br'] as const).map((corner) => (
              <div
                key={corner}
                className={cn(
                  'absolute h-8 w-8',
                  corner === 'tl' && 'left-0 top-0 border-l-2 border-t-2 rounded-tl-sm',
                  corner === 'tr' && 'right-0 top-0 border-r-2 border-t-2 rounded-tr-sm',
                  corner === 'bl' && 'bottom-0 left-0 border-b-2 border-l-2 rounded-bl-sm',
                  corner === 'br' && 'bottom-0 right-0 border-b-2 border-r-2 rounded-br-sm',
                  quality.score >= 80 ? 'border-success-400' : 'border-white/70',
                  'transition-colors duration-300',
                )}
              />
            ))}
          </div>
        )}

        {/* Countdown overlay */}
        {state === 'countdown' && (
          <div className="absolute inset-0 flex items-center justify-center" aria-live="assertive">
            <span
              className="text-white font-bold tabular-nums"
              style={{ fontSize: '120px', textShadow: '0 2px 20px rgba(0,0,0,0.5)' }}
              aria-label={t('camera.countdown', { count: countdown })}
            >
              {countdown}
            </span>
          </div>
        )}

        {/* Low quality warning (preview state) */}
        {state === 'preview' && lowQualityWarning && (
          <div role="alert" className="absolute bottom-0 left-0 right-0 bg-warning-600/90 px-4 py-3">
            <p className="text-white text-sm font-medium">{t('camera.warning.low_quality')}</p>
            <p className="text-white/80 text-xs mt-1">{t('camera.warning.low_quality_hint')}</p>
          </div>
        )}
      </div>

      {/* Bottom controls */}
      <div className="px-6 pb-safe-bottom pb-8 pt-4 bg-black">
        {state === 'active' || state === 'countdown' ? (
          <>
            {/* Quality bar */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-white/70" aria-live="polite">{qualityLabel()}</span>
                <span className="text-xs font-medium" style={{ color: qualityColor }}>
                  {quality.score}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-white/20 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{ width: `${quality.score}%`, backgroundColor: qualityColor }}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={quality.score}
                  aria-label={t('camera.quality.label')}
                />
              </div>
              {quality.score >= 80 && (
                <p className="text-xs text-success-400 mt-1 text-center" aria-live="polite">
                  {t('camera.quality.auto_capture')}
                </p>
              )}
            </div>

            {/* Capture button */}
            <div className="flex items-center justify-center gap-8">
              <div className="w-10" />
              <button
                onClick={() => captureFrame()}
                disabled={state === 'countdown'}
                className={cn(
                  'relative h-16 w-16 rounded-full border-4 border-white flex items-center justify-center',
                  'transition-transform active:scale-95',
                  state === 'countdown' && 'opacity-50 cursor-not-allowed',
                )}
                aria-label={t('camera.capture')}
              >
                <div className="h-12 w-12 rounded-full bg-white" />
              </button>
              {/* Flip camera */}
              <button
                onClick={() => setFacingMode((f) => (f === 'environment' ? 'user' : 'environment'))}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white"
                aria-label={t('camera.flip')}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
          </>
        ) : state === 'preview' ? (
          <div className="flex gap-3">
            <button
              onClick={retake}
              className="flex-1 rounded-card border border-white/30 py-3 text-sm font-medium text-white min-h-touch"
              aria-label={t('camera.retake')}
            >
              {t('camera.retake')}
            </button>
            <button
              onClick={confirmCapture}
              className="flex-1 rounded-card bg-brand-500 py-3 text-sm font-medium text-white min-h-touch"
              aria-label={t('camera.use_photo')}
            >
              {t('camera.use_photo')}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-center h-16">
            <div className="h-6 w-6 rounded-full border-2 border-white/30 border-t-white animate-spin" aria-label={t('camera.loading')} />
          </div>
        )}
      </div>
    </div>
  )
}
