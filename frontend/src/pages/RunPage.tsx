import { ClipboardList, Lock, RefreshCw, Wifi } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useParams } from "react-router"

import { ErrorBox, Loading, Mono } from "@/components/PageState"
import { ChecksPanel } from "@/components/run/ChecksPanel"
import { DecisionHeader } from "@/components/run/DecisionHeader"
import { DocumentsPanel } from "@/components/run/DocumentsPanel"
import { EmailPanel } from "@/components/run/EmailPanel"
import { Section } from "@/components/run/Section"
import { StageTimeline } from "@/components/run/StageTimeline"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useRunStream } from "@/hooks/useRunStream"
import { api, type RunDetail, type StageName, type StageResult } from "@/lib/api"

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  )
}

function ConnectionNote({ connection }: { connection: string }) {
  if (connection === "reconnecting") {
    return <p className="flex items-center gap-1.5 text-xs text-pending"><Wifi className="size-3.5" aria-hidden /> Connection lost, reconnecting…</p>
  }
  return null
}

function Result({ run, onEmailChange }: { run: RunDetail; onEmailChange: (run: RunDetail) => void }) {
  const decision = run.decision
  return (
    <div className="space-y-6">
      <DecisionHeader run={run} />
      {decision && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Section title="Why" icon={<ClipboardList className="size-4" />}>
            <BulletList items={decision.reasons} />
          </Section>
          {decision.status === "PENDING" ? (
            <Section
              title="What the vendor must do"
              description="These are the only instructions that ever reach the vendor."
              action={
                <Button asChild size="sm">
                  <Link to={`/submit?resubmit=${encodeURIComponent(run.vendor_id)}`}>
                    <RefreshCw className="size-4" aria-hidden /> Resubmit for this vendor
                  </Link>
                </Button>
              }
            >
              {decision.missing_items.length ? (
                <BulletList items={decision.missing_items} />
              ) : (
                <p className="text-sm text-muted-foreground">Nothing for the vendor to fix: a person needs to review this vendor.</p>
              )}
            </Section>
          ) : null}
          {decision.review_notes.length > 0 && (
            <Section
              title="Internal review notes"
              icon={<Lock className="size-4" />}
              description="For the procurement team only. Never sent to the vendor."
              className="border-internal/30 bg-internal-soft/40"
            >
              <BulletList items={decision.review_notes} />
            </Section>
          )}
        </div>
      )}
      <ChecksPanel run={run} />
      <DocumentsPanel run={run} />
      {run.email && (
        <EmailPanel runId={run.run_id} email={run.email} onChange={(email) => onEmailChange({ ...run, email })} />
      )}
    </div>
  )
}

export function RunPage() {
  const { runId = "" } = useParams()
  return <RunView key={runId} runId={runId} /> // a new run id starts with fresh state
}

function RunView({ runId }: { runId: string }) {
  const stream = useRunStream(runId)
  const [run, setRun] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const finished = Boolean(stream.done || stream.serverError || stream.failed)

  // Once the stream says the run is over (or could not be opened), load the full saved result.
  useEffect(() => {
    if (!finished) return
    let cancelled = false
    api.run(runId).then(
      (detail) => !cancelled && setRun(detail),
      (e: Error) => !cancelled && setError(e.message),
    )
    return () => { cancelled = true }
  }, [finished, runId])

  const stages: Partial<Record<StageName, StageResult>> = run
    ? Object.fromEntries(run.stages.map((s) => [s.stage, s]))
    : stream.stages

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <Card>
          <CardContent className="space-y-3">
            <div>
              <h2 className="font-semibold">Pipeline</h2>
              <p className="text-xs text-muted-foreground">Run <Mono>{runId.slice(0, 8)}</Mono></p>
            </div>
            <ConnectionNote connection={stream.connection} />
            {stream.serverError && <p className="text-sm text-pending">{stream.serverError}</p>}
            <StageTimeline stages={stages} />
          </CardContent>
        </Card>
      </aside>
      <section className="min-w-0">
        {run ? (
          <Result run={run} onEmailChange={setRun} />
        ) : error ? (
          <ErrorBox
            title={stream.failed ? "Run not found" : "Could not load the result"}
            message={error}
            onRetry={() => { setError(null); api.run(runId).then(setRun, (e: Error) => setError(e.message)) }}
          />
        ) : (
          <Card>
            <CardContent>
              <Loading label={finished ? "Loading the result…" : "Checking this vendor… each stage appears on the left as it finishes."} />
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  )
}
