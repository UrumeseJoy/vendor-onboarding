import { ChevronRight, ListChecks } from "lucide-react"

import { CheckResultIcon, StageStatusBadge } from "@/components/StatusBadge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import type { CheckOutcome, RunDetail } from "@/lib/api"
import { STAGE_LABELS } from "@/lib/format"
import { Section } from "./Section"
import { ScoreBar } from "./ScoreBar"

const HIDDEN_DETAILS = new Set(["action_required", "review_note", "score", "mismatches", "low_confidence_fields"])

function DetailValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) return <>{value.length ? value.map(String).join(", ") : "—"}</>
  if (value && typeof value === "object") return <>{JSON.stringify(value)}</>
  return <>{String(value)}</>
}

function CheckRow({ check, thresholds }: { check: CheckOutcome; thresholds: RunDetail["thresholds"] }) {
  const d = check.details
  const simple = Object.entries(d).filter(([k, v]) => !HIDDEN_DETAILS.has(k) && v !== null && v !== "" && typeof v !== "object")
  const lists = Object.entries(d).filter(([k, v]) => !HIDDEN_DETAILS.has(k) && Array.isArray(v) && v.length)
  const mismatches = (d.mismatches as { field: string; form_value: string; document_value: string }[] | undefined) ?? []
  return (
    <li className="flex gap-3 py-2.5">
      <CheckResultIcon result={check.result} className="mt-0.5" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs font-medium">{check.check_id}</span>
          <span className="rounded border px-1.5 text-[10px] font-medium text-muted-foreground">{check.severity}</span>
        </div>
        <p className="text-sm">{check.reason}</p>
        {typeof d.score === "number" && check.check_id === "BANK_NAME_MATCH" && (
          <ScoreBar score={d.score} warn={thresholds.name_warn} pass={thresholds.name_pass} />
        )}
        {mismatches.length > 0 && (
          <ul className="text-xs text-muted-foreground">
            {mismatches.map((m) => (
              <li key={m.field}>
                <span className="font-mono">{m.field}</span>: document <span className="font-mono">{m.document_value}</span> vs
                form <span className="font-mono">{m.form_value}</span>
              </li>
            ))}
          </ul>
        )}
        {(simple.length > 0 || lists.length > 0) && (
          <dl className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
            {[...simple, ...lists].map(([key, value]) => (
              <div key={key} className="flex gap-1">
                <dt>{key.replace(/_/g, " ")}:</dt>
                <dd className="font-mono"><DetailValue value={value} /></dd>
              </div>
            ))}
          </dl>
        )}
        {typeof d.action_required === "string" && (
          <p className="text-xs"><span className="font-medium">Vendor action:</span> {d.action_required}</p>
        )}
        {typeof d.review_note === "string" && (
          <p className="rounded bg-internal-soft px-2 py-1 text-xs text-internal">
            <span className="font-medium">Internal note:</span> {d.review_note}
          </p>
        )}
      </div>
    </li>
  )
}

export function ChecksPanel({ run }: { run: RunDetail }) {
  return (
    <Section title="Checks" icon={<ListChecks className="size-4" />} description="Every check, grouped by stage. Stages with problems start open.">
      <div className="divide-y">
        {run.stages.filter((s) => s.checks.length > 0).map((stage) => {
          const problems = stage.checks.filter((c) => c.result !== "PASS").length
          return (
            <Collapsible key={stage.stage} defaultOpen={problems > 0} className="group py-1">
              <CollapsibleTrigger className="flex w-full items-center gap-2 rounded-md py-2 text-left hover:bg-muted/50">
                <ChevronRight className="size-4 transition-transform group-data-[state=open]:rotate-90" aria-hidden />
                <span className="font-medium">{STAGE_LABELS[stage.stage]}</span>
                <span className="text-xs text-muted-foreground">
                  {stage.checks.length} check{stage.checks.length === 1 ? "" : "s"}
                  {problems > 0 && ` · ${problems} need attention`}
                </span>
                <span className="ml-auto"><StageStatusBadge status={stage.status} /></span>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <ul className="divide-y pl-6">
                  {stage.checks.map((check, i) => (
                    <CheckRow key={`${check.check_id}-${i}`} check={check} thresholds={run.thresholds} />
                  ))}
                </ul>
              </CollapsibleContent>
            </Collapsible>
          )
        })}
      </div>
    </Section>
  )
}
