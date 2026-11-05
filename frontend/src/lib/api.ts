// One typed client for the backend API. Every response the UI uses has a type here.

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000"

// ---------- types (mirror backend/app/models.py and main.py) ----------

export type VendorStatus = "APPROVED" | "PENDING" | "REJECTED"
export type DisplayStatus = VendorStatus | "PROCESSING"
export type CheckResult = "PASS" | "FAIL" | "WARN"
export type Severity = "HARD" | "SOFT"
export type StageStatus = "WAITING" | "RUNNING" | "PASSED" | "WARNING" | "FAILED" | "SKIPPED"
export type Country = "IN" | "US"
export type DocType =
  | "GST_CERTIFICATE" | "PAN_CARD" | "CANCELLED_CHEQUE" | "BANK_LETTER" | "W9_FORM" | "INVOICE" | "UNKNOWN"

export const STAGES = [
  "INTAKE", "EXTRACTION", "COMPLETENESS", "FORMAT", "CROSS_CHECK", "RISK", "DECISION", "VENDOR_MESSAGE",
] as const
export type StageName = (typeof STAGES)[number]

export interface CheckOutcome {
  check_id: string
  stage: StageName
  result: CheckResult
  severity: Severity
  reason: string
  details: Record<string, unknown>
}

export interface StageResult {
  stage: StageName
  status: StageStatus
  checks: CheckOutcome[]
  started_at: string | null
  finished_at: string | null
  summary: string
}

export interface Decision {
  vendor_id: string
  status: VendorStatus
  reasons: string[]
  missing_items: string[]
  risk_score: number
  decided_by: string
  review_notes: string[]
  checks_summary: Partial<Record<CheckResult, number>>
}

export interface ExtractedDocument {
  filename: string
  slot: DocType
  detected_type: DocType
  fields: Record<string, string>
  field_confidence: Record<string, number>
  overall_confidence: number
  notes: string[]
}

export interface VendorEmail {
  subject: string
  body: string
  generated_by: "ai" | "template"
  status: "DRAFT" | "SENT"
  approved_at: string | null
  edited: boolean
  fallback_reason: string | null
}

export interface BankDetails {
  holder_name: string
  account_number: string // always masked when it comes from the API
  ifsc?: string | null
  routing_number?: string | null
  bank_country: Country
}

export interface UploadedDocument {
  slot: DocType
  filename: string
}

export interface VendorSubmission {
  legal_name: string
  country: Country
  state: string
  address: string
  contact_email: string
  pan?: string | null
  gstin?: string | null
  ein?: string | null
  bank: BankDetails
  documents: UploadedDocument[]
}

export interface RunDetail {
  run_id: string
  vendor_id: string
  started_at: string
  finished_at: string | null
  stages: StageResult[]
  decision: Decision | null
  had_errors: boolean
  upload_id: string | null
  email: VendorEmail | null
  documents: ExtractedDocument[]
  run_number: number
  submission: VendorSubmission
  thresholds: { name_pass: number; name_warn: number; min_field_confidence: number }
}

export interface Health {
  status: string
  extractor_mode: string
  demo_mode: boolean
}

export interface DemoCase {
  case_id: string
  title: string
  description: string
  expected_status: VendorStatus
}

export interface DemoCaseDetail extends DemoCase {
  submission: VendorSubmission
  documents: (UploadedDocument & { file_url: string })[]
}

export interface Started {
  run_id: string
  vendor_id: string
}

export interface VendorSummary {
  vendor_id: string
  legal_name: string
  country: Country
  status: DisplayStatus
  risk_score: number
  run_count: number
  updated_at: string
}

export interface RunSummary {
  run_id: string
  run_number: number
  status: VendorStatus
  risk_score: number
  started_at: string
  finished_at: string | null
  had_errors: boolean
}

export interface VendorDetail extends VendorSummary {
  account_last4: string | null
  latest_run_id: string | null
  created_at: string
  runs: RunSummary[]
}

export interface Stats {
  status_counts: Record<VendorStatus, number>
  total_vendors: number
  total_runs: number
}

export interface DoneEvent {
  run_id: string
  vendor_id: string
  decision: Decision | null
}

// ---------- client ----------

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Turn FastAPI's {"detail": ...} into one readable sentence. */
function readableDetail(detail: unknown): string {
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".") || "request"}: ${d.msg ?? ""}`)
      .join("; ")
  }
  return "Something went wrong."
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, init)
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}.`)
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      message = readableDetail((await response.json()).detail)
    } catch {
      /* not JSON: keep the status text */
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body ?? {}),
})

export const api = {
  health: () => request<Health>("/api/health"),
  stats: () => request<Stats>("/api/stats"),
  vendors: () => request<VendorSummary[]>("/api/vendors"),
  vendor: (vendorId: string) => request<VendorDetail>(`/api/vendors/${encodeURIComponent(vendorId)}`),
  run: (runId: string) => request<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`),
  demoCases: () => request<DemoCase[]>("/api/demo-cases"),
  demoCase: (caseId: string) => request<DemoCaseDetail>(`/api/demo-cases/${encodeURIComponent(caseId)}`),

  runDemoCase: (caseId: string, vendorId?: string) =>
    request<Started>(`/api/demo-cases/${encodeURIComponent(caseId)}/run`, json(vendorId ? { vendor_id: vendorId } : {})),

  /** New vendor, or a resubmission when resubmitVendorId is given. */
  submit: (submission: VendorSubmission, files: File[], resubmitVendorId?: string) => {
    const form = new FormData()
    form.append("submission", JSON.stringify(submission))
    for (const file of files) form.append("files", file, file.name)
    const path = resubmitVendorId
      ? `/api/vendors/${encodeURIComponent(resubmitVendorId)}/resubmit`
      : "/api/vendors"
    return request<Started>(path, { method: "POST", body: form })
  },

  approveEmail: (runId: string, edits?: { subject?: string; body?: string }) =>
    request<VendorEmail>(`/api/runs/${encodeURIComponent(runId)}/email/approve`, json(edits ?? {})),

  resetDemo: () => request<{ deleted_vendors: number; deleted_runs: number }>("/api/admin/reset-demo", json({})),
}

export const eventsUrl = (runId: string) => `${API_URL}/api/runs/${encodeURIComponent(runId)}/events`
export const runDocumentUrl = (runId: string, filename: string) =>
  `${API_URL}/api/runs/${encodeURIComponent(runId)}/documents/${encodeURIComponent(filename)}`
export const absoluteUrl = (path: string) => `${API_URL}${path}`
