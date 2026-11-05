import { FileText, Upload, X } from "lucide-react"
import { useRef, useState, type DragEvent } from "react"

import { Button } from "@/components/ui/button"
import { fileProblem } from "@/lib/files"
import { cn } from "@/lib/utils"

export function FileDrop({ id, label, file, onChange }: {
  id: string; label: string; file: File | null; onChange: (file: File | null) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  const accept = (picked: File | undefined) => {
    if (!picked) return
    const issue = fileProblem(picked)
    setProblem(issue)
    if (!issue) onChange(picked)
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    accept(event.dataTransfer.files[0])
  }

  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">{label}</div>
      {file ? (
        <div className="flex items-center gap-2 rounded-sm border px-3 py-2 text-sm">
          <FileText className="size-4 text-muted-foreground" aria-hidden />
          <span className="min-w-0 flex-1 truncate font-mono text-xs">{file.name}</span>
          <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</span>
          <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${file.name}`} onClick={() => onChange(null)}>
            <X className="size-4" />
          </Button>
        </div>
      ) : (
        <label
          htmlFor={id}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-1 rounded-sm border border-dashed border-border-strong px-3 py-4 text-center text-sm text-muted-foreground transition-colors hover:bg-muted",
            dragging && "border-primary bg-brand-tint",
          )}
        >
          <Upload className="size-4" aria-hidden />
          <span>Drop a PDF here or <span className="font-medium text-brand">browse</span></span>
          <span className="text-xs">PDF only, up to 10 MB</span>
        </label>
      )}
      <input
        ref={input}
        id={id}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => { accept(e.target.files?.[0]); e.target.value = "" }}
      />
      {problem && <p className="mt-1 text-xs text-rejected">{problem}</p>}
    </div>
  )
}
