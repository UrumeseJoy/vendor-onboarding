import { STAGE, TONE_TEXT } from "@/lib/status"
import { STAGES, type StageName, type StageResult } from "@/lib/api"
import { STAGE_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"
import { CheckResultIcon } from "@/components/StatusBadge"

/** The 8 stages as a vertical timeline: waiting → running → passed / warning / failed / skipped. */
export function StageTimeline({ stages }: { stages: Partial<Record<StageName, StageResult>> }) {
  return (
    <ol className="relative" aria-label="Pipeline stages">
      {STAGES.map((name, index) => {
        const stage = stages[name]
        const status = stage?.status ?? "WAITING"
        const meta = STAGE[status]
        const Icon = meta.icon
        const problems = stage?.checks.filter((c) => c.result !== "PASS") ?? []
        const last = index === STAGES.length - 1
        const toneClass = status === "RUNNING" ? "text-brand" : TONE_TEXT[meta.tone] // running is red; finished stages keep status colours
        return (
          <li key={name} className="relative flex gap-3 pb-3 last:pb-0">
            {!last && <span className="absolute top-6 left-[11px] h-[calc(100%-1.5rem)] w-px bg-border" aria-hidden />}
            <span
              className={cn(
                "relative z-10 flex size-6 shrink-0 items-center justify-center rounded-sm border bg-background",
                toneClass,
              )}
            >
              <Icon className={cn("size-3.5", status === "RUNNING" && "animate-spin")} aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className={cn("text-sm font-semibold", status === "WAITING" && "font-medium text-muted-foreground")}>
                  {STAGE_LABELS[name]}
                </span>
                <span className={cn("text-xs font-medium", toneClass)}>{meta.label}</span>
              </div>
              {stage?.summary && <p className="text-xs text-muted-foreground">{stage.summary}</p>}
              {problems.length > 0 && (
                <ul className="mt-1.5 space-y-1">
                  {problems.map((check, i) => (
                    <li key={`${check.check_id}-${i}`} className="flex gap-2 text-xs">
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
