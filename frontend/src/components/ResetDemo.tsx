import { RotateCcw } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

/** Sidebar item under "Demo": asks for confirmation, then deletes all demo data. */
export function ResetDemo({ onDone, itemClass }: { onDone: () => void; itemClass: string }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.resetDemo()
      setConfirming(false)
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!confirming) {
    return (
      <button type="button" className={cn(itemClass, "w-full text-left")} onClick={() => setConfirming(true)}>
        <RotateCcw className="size-4" aria-hidden /> Reset demo
      </button>
    )
  }
  return (
    <div className="mx-3 space-y-2 rounded-sm border border-rejected bg-rejected-soft p-2.5 text-xs text-rejected">
      <p>Delete all vendors, runs and uploads?</p>
      <div className="flex gap-2">
        <Button size="sm" variant="destructive" onClick={reset} disabled={busy}>{busy ? "Resetting…" : "Yes, reset"}</Button>
        <Button size="sm" variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
      </div>
      {error && <p>{error}</p>}
    </div>
  )
}
