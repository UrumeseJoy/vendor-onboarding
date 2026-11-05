import { CircleCheck, CircleDashed, CircleX, Clock, LoaderCircle, TriangleAlert, type LucideIcon } from "lucide-react"

import type { CheckResult, DisplayStatus, StageStatus } from "./api"

// One mapping from every status to its tone, icon and word, used everywhere in the UI.

export type Tone = "approved" | "pending" | "rejected" | "processing" | "neutral"

export interface StatusMeta {
  tone: Tone
  icon: LucideIcon
  label: string
}

export const TONE_PILL: Record<Tone, string> = {
  approved: "bg-approved-soft text-approved",
  pending: "bg-pending-soft text-pending",
  rejected: "bg-rejected-soft text-rejected",
  processing: "bg-processing-soft text-processing",
  neutral: "bg-secondary text-muted-foreground",
}

export const TONE_TEXT: Record<Tone, string> = {
  approved: "text-approved",
  pending: "text-pending",
  rejected: "text-rejected",
  processing: "text-processing",
  neutral: "text-muted-foreground",
}

export const VENDOR: Record<DisplayStatus, StatusMeta> = {
  APPROVED: { tone: "approved", icon: CircleCheck, label: "Approved" },
  PENDING: { tone: "pending", icon: TriangleAlert, label: "Pending" },
  REJECTED: { tone: "rejected", icon: CircleX, label: "Rejected" },
  PROCESSING: { tone: "processing", icon: LoaderCircle, label: "Processing" },
}

export const CHECK: Record<CheckResult, StatusMeta> = {
  PASS: { tone: "approved", icon: CircleCheck, label: "Pass" },
  WARN: { tone: "pending", icon: TriangleAlert, label: "Warning" },
  FAIL: { tone: "rejected", icon: CircleX, label: "Fail" },
}

export const STAGE: Record<StageStatus, StatusMeta> = {
  WAITING: { tone: "neutral", icon: Clock, label: "Waiting" },
  RUNNING: { tone: "processing", icon: LoaderCircle, label: "Running" },
  PASSED: { tone: "approved", icon: CircleCheck, label: "Passed" },
  WARNING: { tone: "pending", icon: TriangleAlert, label: "Warning" },
  FAILED: { tone: "rejected", icon: CircleX, label: "Failed" },
  SKIPPED: { tone: "neutral", icon: CircleDashed, label: "Skipped" },
}

export const UNKNOWN_STATUS: StatusMeta = { tone: "neutral", icon: CircleDashed, label: "Unknown" }
