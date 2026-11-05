import { ChevronRight } from "lucide-react"

import { CheckResultBadge, StageStatusBadge } from "@/components/StatusBadge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
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
    <TableRow className="align-top">
      <TableCell className="h-auto py-2.5"><CheckResultBadge result={check.result} /></TableCell>
      <TableCell className="h-auto py-2.5"><span className="font-mono text-xs font-medium">{check.check_id}</span></TableCell>
      <TableCell className="h-auto py-2.5">
        <span className="rounded-sm bg-secondary px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">{check.severity}</span>
      </TableCell>
      <TableCell className="h-auto min-w-64 py-2.5 whitespace-normal">
        <div className="space-y-1.5">
          <p>{check.reason}</p>
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
            <p className="text-xs"><span className="font-semibold">Vendor action:</span> {d.action_required}</p>
          )}
          {typeof d.review_note === "string" && (
            <p className="rounded-sm bg-internal-soft px-2 py-1 text-xs text-internal">
              <span className="font-semibold">Internal note:</span> {d.review_note}
            </p>
          )}
        </div>
      </TableCell>
    </TableRow>
  )
}

export function ChecksPanel({ run }: { run: RunDetail }) {
  return (
    <Section title="Checks" description="Every check, grouped by stage. Stages with problems start open." flush>
      <div className="divide-y">
        {run.stages.filter((s) => s.checks.length > 0).map((stage) => {
          const problems = stage.checks.filter((c) => c.result !== "PASS").length
          return (
            <Collapsible key={stage.stage} defaultOpen={problems > 0} className="group">
              <CollapsibleTrigger className="flex min-h-10 w-full items-center gap-2 px-4 py-2 text-left hover:bg-muted">
                <ChevronRight className="size-4 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" aria-hidden />
                <span className="font-semibold">{STAGE_LABELS[stage.stage]}</span>
                <span className="text-xs text-muted-foreground">
                  {stage.checks.length} check{stage.checks.length === 1 ? "" : "s"}
                  {problems > 0 && ` · ${problems} need attention`}
                </span>
                <span className="ml-auto"><StageStatusBadge status={stage.status} /></span>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="overflow-x-auto border-t">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-24">Result</TableHead>
                        <TableHead>Check ID</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead>Reason</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {stage.checks.map((check, i) => (
                        <CheckRow key={`${check.check_id}-${i}`} check={check} thresholds={run.thresholds} />
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CollapsibleContent>
            </Collapsible>
          )
        })}
      </div>
    </Section>
  )
}
