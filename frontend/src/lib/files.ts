export const MAX_BYTES = 10 * 1024 * 1024

/** Client-side check before upload; the server checks again. */
export function fileProblem(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf")) return `${file.name} is not a PDF.`
  if (file.size > MAX_BYTES) return `${file.name} is larger than 10 MB.`
  return null
}
