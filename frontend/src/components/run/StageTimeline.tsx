import { STAGE, TONE_TEXT } from "@/lib/status"
import { STAGES, type StageName, type StageResult } from "@/lib/api"
import { STAGE_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"
import { CheckResultIcon } from "@/components/StatusBadge"

/** The 8 stages as a vertical timeline: waiting → running → passed / warning / failed / skipped. */
export function StageTimeline({ stages }: { stages: Partial<Record<StageName, StageResult>> }) {
  return (
    <ol className="relative space-y-1" aria-label="Pipeline stages">
      {STAGES.map((name, index) => {
        const stage = stages[name]
        const status = stage?.status ?? "WAITING"
        const meta = STAGE[status]
        const Icon = meta.icon
        const problems = stage?.checks.filter((c) => c.result !== "PASS") ?? []
        const last = index === STAGES.length - 1
        return (
          <li key={name} className="relative flex gap-3 pb-3">
            {!last && <span className="absolute top-7 left-[13px] h-[calc(100%-1.25rem)] w-px bg-border" aria-hidden />}
            <span
              className={cn(
                "relative z-10 mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border bg-background",
                TONE_TEXT[meta.tone],
              )}
            >
              <Icon className={cn("size-4", status === "RUNNING" && "animate-spin")} aria-hidden />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className={cn("font-medium", status === "WAITING" && "text-muted-foreground")}>
                  {STAGE_LABELS[name]}
                </span>
                <span className={cn("text-xs font-medium", TONE_TEXT[meta.tone])}>{meta.label}</span>
              </div>
              {stage?.summary && <p className="text-sm text-muted-foreground">{stage.summary}</p>}
              {problems.length > 0 && (
                <ul className="mt-1.5 space-y-1">
                  {problems.map((check, i) => (
                    <li key={`${check.check_id}-${i}`} className="flex gap-2 text-sm">
                      <CheckResultIcon result={check.result} className="mt-0.5" />
                      <span>
                        <span className="font-mono text-xs text-muted-foreground">{check.check_id}</span>{" "}
                        {check.reason}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
