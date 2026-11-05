import type { CheckResult, DisplayStatus, StageStatus } from "@/lib/api"
import { CHECK, STAGE, TONE_PILL, TONE_TEXT, UNKNOWN_STATUS, VENDOR, type StatusMeta } from "@/lib/status"
import { cn } from "@/lib/utils"

// Status is always shown as colour + icon + word, never colour alone.

function Pill({ meta, size = "sm", spin }: { meta: StatusMeta; size?: "sm" | "lg"; spin?: boolean }) {
  const Icon = meta.icon
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm font-semibold whitespace-nowrap",
        size === "lg" ? "px-2.5 py-1 text-sm" : "px-1.5 py-0.5 text-xs",
        TONE_PILL[meta.tone],
      )}
    >
      <Icon className={cn(size === "lg" ? "size-4" : "size-3", spin && "animate-spin")} aria-hidden />
      {meta.label}
    </span>
  )
}

export function VendorStatusBadge({ status, size }: { status: string; size?: "sm" | "lg" }) {
  const meta = VENDOR[status as DisplayStatus] ?? { ...UNKNOWN_STATUS, label: status }
  return <Pill meta={meta} size={size} spin={status === "PROCESSING"} />
}

export function CheckResultBadge({ result }: { result: CheckResult }) {
  return <Pill meta={CHECK[result]} />
}

export function StageStatusBadge({ status }: { status: StageStatus }) {
  return <Pill meta={STAGE[status]} spin={status === "RUNNING"} />
}

export function CheckResultIcon({ result, className }: { result: CheckResult; className?: string }) {
  const { icon: Icon, tone, label } = CHECK[result]
  return <Icon className={cn("size-4 shrink-0", TONE_TEXT[tone], className)} aria-label={label} />
}
