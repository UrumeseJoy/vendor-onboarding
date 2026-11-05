import { RefreshCw, Wifi } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useParams } from "react-router"

import { Breadcrumb, ErrorBox, Loading, Mono } from "@/components/PageState"
import { Panel } from "@/components/Panel"
import { ChecksPanel } from "@/components/run/ChecksPanel"
import { DecisionHeader } from "@/components/run/DecisionHeader"
import { DocumentsPanel } from "@/components/run/DocumentsPanel"
import { EmailPanel } from "@/components/run/EmailPanel"
import { Section } from "@/components/run/Section"
import { StageTimeline } from "@/components/run/StageTimeline"
import { Button } from "@/components/ui/button"
import { useRunStream } from "@/hooks/useRunStream"
import { api, type RunDetail, type StageName, type StageResult } from "@/lib/api"

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
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
    <div className="space-y-4">
      <DecisionHeader run={run} />
      {decision && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Section title="Why">
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
              description="For the procurement team only. Never sent to the vendor."
              action={<span className="rounded-sm bg-secondary px-1.5 py-0.5 text-xs font-semibold text-muted-foreground">Internal</span>}
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
    <div>
    <Breadcrumb
      items={run
        ? [{ label: "Vendors", to: "/" }, { label: run.vendor_id, to: `/vendors/${encodeURIComponent(run.vendor_id)}` }, { label: `Run ${run.run_number}` }]
        : [{ label: "Vendors", to: "/" }, { label: `Run ${runId.slice(0, 8)}` }]}
    />
    <div className="grid gap-4 lg:grid-cols-[minmax(0,19rem)_minmax(0,1fr)]">
      <aside className="lg:sticky lg:top-[74px] lg:self-start">
        <Panel title="Pipeline" description={<>Run <Mono>{runId.slice(0, 8)}</Mono></>}>
          <div className="space-y-3">
            <ConnectionNote connection={stream.connection} />
            {stream.serverError && <p className="text-sm text-pending">{stream.serverError}</p>}
            <StageTimeline stages={stages} />
          </div>
        </Panel>
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
          <Panel>
            <Loading label={finished ? "Loading the result…" : "Checking this vendor… each stage appears on the left as it finishes."} />
          </Panel>
        )}
      </section>
    </div>
    </div>
  )
}
