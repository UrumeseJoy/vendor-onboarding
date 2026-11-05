import type { DocType, StageName } from "./api"

/** The backend stores some times without a timezone (SQLite drops it); they are UTC. */
export function parseDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`)
}

export function relativeTime(value: string, now = Date.now()): string {
  const seconds = Math.round((now - parseDate(value).getTime()) / 1000)
  if (seconds < 45) return "just now"
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

export function dateTime(value: string | null): string {
  if (!value) return "—"
  return parseDate(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
}

export const STAGE_LABELS: Record<StageName, string> = {
  INTAKE: "Intake",
  EXTRACTION: "Document reading",
  COMPLETENESS: "Completeness",
  FORMAT: "Format checks",
  CROSS_CHECK: "Cross-checks",
  RISK: "Risk flags",
  DECISION: "Decision",
  VENDOR_MESSAGE: "Vendor message",
}

export const DOC_LABELS: Record<DocType, string> = {
  GST_CERTIFICATE: "GST certificate",
  PAN_CARD: "PAN card",
  CANCELLED_CHEQUE: "Cancelled cheque",
  BANK_LETTER: "Bank letter",
  W9_FORM: "Form W-9",
  INVOICE: "Invoice",
  UNKNOWN: "Unrecognised",
}

const FIELD_LABELS: Record<string, string> = {
  legal_name: "Legal name",
  trade_name: "Trade name",
  pan: "PAN",
  gstin: "GSTIN",
  ein: "EIN",
  holder_name: "Account holder",
  account_number: "Account number",
  ifsc: "IFSC",
  routing_number: "Routing number",
  bank_name: "Bank name",
  address: "Address",
  state: "State",
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  total_amount: "Total amount",
  buyer_name: "Buyer",
}

export const fieldLabel = (name: string) => FIELD_LABELS[name] ?? name.replace(/_/g, " ")

/** Fields shown in monospace (identifiers). */
export const MONO_FIELDS = new Set(["pan", "gstin", "ein", "ifsc", "routing_number", "account_number"])

export const percent = (value: number) => `${Math.round(value * 100)}%`
