import { useEffect, useState, type ReactNode } from "react"

import { HealthContext, type HealthState } from "@/hooks/health-context"
import { api } from "@/lib/api"

const POLL_MS = 10_000

/** Checks /api/health every 10 s so the whole app knows the extractor mode and whether the backend is up. */
export function HealthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<HealthState>({ health: null, offline: false })

  useEffect(() => {
    let cancelled = false
    const check = () =>
      api.health().then(
        (health) => !cancelled && setState({ health, offline: false }),
        () => !cancelled && setState((s) => ({ ...s, offline: true })),
      )
    check()
    const timer = setInterval(check, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  return <HealthContext.Provider value={state}>{children}</HealthContext.Provider>
}
