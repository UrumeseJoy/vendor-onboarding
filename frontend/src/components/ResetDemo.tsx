import { RotateCcw } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useHealth } from "@/hooks/useHealth"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

const TOKEN_KEY = "adminToken"

// The admin token lives in sessionStorage only: gone when the tab closes, never in localStorage or code.
function savedToken(): string {
  try { return sessionStorage.getItem(TOKEN_KEY) ?? "" } catch { return "" }
}
function saveToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private mode: the token just isn't remembered */
  }
}

/** Sidebar item under "Demo": asks for confirmation (and the admin token if the server needs one), then deletes all demo data. */
export function ResetDemo({ onDone, itemClass }: { onDone: () => void; itemClass: string }) {
  const { health } = useHealth()
  const needsToken = health?.reset_requires_token ?? false
  const [token, setToken] = useState(savedToken)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.resetDemo(needsToken ? token.trim() : undefined)
      if (needsToken) saveToken(token.trim())
      setConfirming(false)
      onDone()
    } catch (e) {
      if (needsToken) { saveToken(null); setToken("") } // a wrong token is not kept
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
      {needsToken && (
        <Input
          type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off"
          aria-label="Admin token" placeholder="Admin token" className="h-8 bg-background text-foreground"
        />
      )}
      <div className="flex gap-2">
        <Button size="sm" variant="destructive" onClick={reset} disabled={busy || (needsToken && !token.trim())}>{busy ? "Resetting…" : "Yes, reset"}</Button>
        <Button size="sm" variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
      </div>
      {error && <p>{error}</p>}
    </div>
  )
}
