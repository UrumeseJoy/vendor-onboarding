import { CircleAlert } from "lucide-react"

import { Mono } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Card, CardContent } from "@/components/ui/card"
import type { RunDetail } from "@/lib/api"
import { dateTime } from "@/lib/format"

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  )
}

export function DecisionHeader({ run }: { run: RunDetail }) {
  const decision = run.decision
  const summary = decision?.checks_summary ?? {}
  return (
    <Card>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{run.submission.legal_name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              <Mono>{run.vendor_id}</Mono> · Run {run.run_number} · {run.submission.country === "IN" ? "India" : "USA"} ·{" "}
              {dateTime(run.finished_at ?? run.started_at)}
            </p>
          </div>
          {decision && <VendorStatusBadge status={decision.status} size="lg" />}
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Risk score" value={`${decision?.risk_score ?? 0} / 100`} />
          <Stat label="Checks passed" value={summary.PASS ?? 0} tone="text-approved" />
          <Stat label="Failed" value={summary.FAIL ?? 0} tone={(summary.FAIL ?? 0) > 0 ? "text-rejected" : ""} />
          <Stat label="Warnings" value={summary.WARN ?? 0} tone={(summary.WARN ?? 0) > 0 ? "text-pending" : ""} />
        </div>
        {run.had_errors && (
          <p className="flex items-center gap-2 rounded-md bg-pending-soft px-3 py-2 text-sm text-pending">
            <CircleAlert className="size-4 shrink-0" aria-hidden />
            A processing error occurred, so this vendor cannot be approved automatically and needs manual review.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
