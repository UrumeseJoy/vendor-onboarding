import { CircleAlert } from "lucide-react"

import { Mono } from "@/components/PageState"
import { Fact } from "@/components/Panel"
import { VendorStatusBadge } from "@/components/StatusBadge"
import type { RunDetail } from "@/lib/api"
import { dateTime } from "@/lib/format"

export function DecisionHeader({ run }: { run: RunDetail }) {
  const decision = run.decision
  const summary = decision?.checks_summary ?? {}
  const failed = summary.FAIL ?? 0
  const warned = summary.WARN ?? 0
  return (
    <section className="overflow-hidden rounded-sm border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-[22px] leading-8 font-semibold">{run.submission.legal_name}</h1>
          <p className="text-sm text-muted-foreground">
            <Mono className="text-foreground">{run.vendor_id}</Mono> · {run.submission.country === "IN" ? "India" : "USA"} ·{" "}
            {dateTime(run.finished_at ?? run.started_at)}
          </p>
        </div>
        {decision && <VendorStatusBadge status={decision.status} size="lg" />}
      </div>
      <dl className="grid grid-cols-2 divide-x divide-y sm:grid-cols-4 sm:divide-y-0 [&>div]:px-4 [&>div]:py-2.5">
        <Fact label="Risk score"><span className="tabular-nums">{decision?.risk_score ?? 0} / 100</span></Fact>
        <Fact label="Run"><span className="tabular-nums">{run.run_number}</span></Fact>
        <Fact label="Checks passed"><span className="tabular-nums text-approved">{summary.PASS ?? 0}</span></Fact>
        <Fact label="Failed / warnings">
          <span className="tabular-nums">
            <span className={failed > 0 ? "text-rejected" : ""}>{failed}</span>
            {" / "}
            <span className={warned > 0 ? "text-pending" : ""}>{warned}</span>
          </span>
        </Fact>
      </dl>
      {run.had_errors && (
        <p className="flex items-center gap-2 border-t bg-pending-soft px-4 py-2 text-sm text-pending">
          <CircleAlert className="size-4 shrink-0" aria-hidden />
          A processing error occurred, so this vendor cannot be approved automatically and needs manual review.
        </p>
      )}
    </section>
  )
}
