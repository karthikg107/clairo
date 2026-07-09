/**
 * Normalise images (including iPhone HEIC) to JPEG before upload.
 *
 * iPhone photos are HEIC/HEIF, which the OCR backend can't read — so an
 * iPhone user photographing a contract got "Something went wrong". iOS
 * Safari can natively decode its own HEIC into an <img>, so drawing it to a
 * canvas and exporting JPEG yields a format the backend already handles
 * (verified end-to-end). It also downscales huge phone photos, which speeds
 * upload and improves OCR.
 *
 * PDFs / DOCX / non-images pass through untouched. Any failure falls back to
 * the original file, so this can never make an upload worse than before.
 */
const MAX_DIMENSION = 2200 // px on the longest edge — plenty for OCR

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image decode failed'))
    img.src = src
  })
}

export async function imageToJpeg(file: File): Promise<File> {
  if (typeof document === 'undefined') return file

  const looksLikeImage =
    file.type.startsWith('image/') || /\.(jpe?g|png|heic|heif)$/i.test(file.name)
  if (!looksLikeImage) return file // PDF / DOCX — leave alone

  const url = URL.createObjectURL(file)
  try {
    const img = await loadImage(url)
    let { width, height } = img
    if (!width || !height) return file

    const scale = Math.min(1, MAX_DIMENSION / Math.max(width, height))
    width = Math.round(width * scale)
    height = Math.round(height * scale)

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(img, 0, 0, width, height)

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.9)
    )
    if (!blob) return file

    const jpegName = file.name.replace(/\.[^.]+$/, '') + '.jpg'
    return new File([blob], jpegName, { type: 'image/jpeg' })
  } catch {
    // Non-Safari browser that can't decode a HEIC, canvas blocked, etc. —
    // send the original and let the backend do its best / show a clear error.
    return file
  } finally {
    URL.revokeObjectURL(url)
  }
}
