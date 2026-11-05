import { useEffect, useState } from "react"

import { eventsUrl, type DoneEvent, type StageName, type StageResult } from "@/lib/api"

export type Connection = "connecting" | "open" | "reconnecting" | "closed"

export interface RunStream {
  stages: Partial<Record<StageName, StageResult>>
  done: DoneEvent | null
  serverError: string | null // the backend published an "error" event (run saved as PENDING)
  connection: Connection
  failed: boolean // the stream could not be opened at all (e.g. unknown run)
}

const initial: RunStream = { stages: {}, done: null, serverError: null, connection: "connecting", failed: false }

/**
 * Follows a run's server-sent events. The backend replays everything already published,
 * so a reconnect (or opening a finished run) rebuilds the same picture.
 */
export function useRunStream(runId: string): RunStream {
  const [state, setState] = useState<RunStream>(initial)

  // State starts fresh for each run because RunPage remounts (key = run id) when the id changes.
  useEffect(() => {
    const source = new EventSource(eventsUrl(runId))

    source.onopen = () => setState((s) => ({ ...s, connection: "open" }))

    source.addEventListener("stage", (event) => {
      const stage = JSON.parse((event as MessageEvent).data) as StageResult
      // Keyed by stage name, so replayed events simply overwrite: no duplicates.
      setState((s) => ({ ...s, stages: { ...s.stages, [stage.stage]: stage } }))
    })

    source.addEventListener("done", (event) => {
      const done = JSON.parse((event as MessageEvent).data) as DoneEvent
      source.close() // otherwise EventSource reconnects when the server ends the stream
      setState((s) => ({ ...s, done, connection: "closed" }))
    })

    // "error" is both the backend's own event (a MessageEvent with data) and the browser's
    // connection-error event (a plain Event).
    source.addEventListener("error", (event) => {
      if (event instanceof MessageEvent && event.data) {
        const { message } = JSON.parse(event.data) as { message: string }
        source.close()
        setState((s) => ({ ...s, serverError: message, connection: "closed" }))
        return
      }
      if (source.readyState === EventSource.CLOSED) {
        setState((s) => (s.done || s.serverError ? s : { ...s, connection: "closed", failed: true }))
      } else {
        setState((s) => ({ ...s, connection: "reconnecting" })) // the browser retries by itself
      }
    })

    return () => source.close()
  }, [runId])

  return state
}
