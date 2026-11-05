import { ExternalLink, FileText, Play } from "lucide-react"
import { useEffect, useState } from "react"

import { ErrorBox, Loading, Mono } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { absoluteUrl, api, type DemoCase, type DemoCaseDetail } from "@/lib/api"
import { DOC_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("text-sm", mono && "font-mono", !value && "text-muted-foreground")}>{value || "—"}</div>
    </div>
  )
}

function Preview({ detail, onRun, running }: { detail: DemoCaseDetail; onRun: () => void; running: boolean }) {
  const s = detail.submission
  const india = s.country === "IN"
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">{s.legal_name}</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">{detail.description}</p>
        </div>
        <Button onClick={onRun} disabled={running}>
          <Play className="size-4" aria-hidden /> {running ? "Starting…" : "Run this sample"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Country" value={india ? "India" : "USA"} />
          <Field label="State" value={s.state} />
          <Field label="Contact email" value={s.contact_email} />
          <div className="sm:col-span-2 lg:col-span-3"><Field label="Address" value={s.address} /></div>
          {india ? (
            <>
              <Field label="PAN" value={s.pan} mono />
              <Field label="GSTIN" value={s.gstin} mono />
            </>
          ) : (
            <Field label="EIN" value={s.ein} mono />
          )}
          <Field label="Bank account holder" value={s.bank.holder_name} />
          <Field label="Account number" value={s.bank.account_number} mono />
          <Field label={india ? "IFSC" : "Routing number"} value={india ? s.bank.ifsc : s.bank.routing_number} mono />
        </div>
        <div>
          <div className="mb-2 text-xs text-muted-foreground">Documents</div>
          <ul className="grid gap-2 sm:grid-cols-2">
            {detail.documents.map((d) => (
              <li key={d.filename}>
                <a
                  href={absoluteUrl(d.file_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted"
                >
                  <FileText className="size-4 text-muted-foreground" aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{DOC_LABELS[d.slot]}</span>
                    <Mono className="block truncate text-xs text-muted-foreground">{d.filename}</Mono>
                  </span>
                  <ExternalLink className="size-3.5 text-muted-foreground" aria-hidden />
                </a>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}

export function SamplePicker({ onRun, running }: { onRun: (caseId: string) => void; running: boolean }) {
  const [cases, setCases] = useState<DemoCase[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<DemoCaseDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.demoCases().then(setCases, (e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    api.demoCase(selected).then((d) => !cancelled && setDetail(d), (e: Error) => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [selected])

  if (error) return <ErrorBox title="Could not load the sample vendors" message={error} />
  if (!cases) return <Loading />

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <ul className="space-y-2" aria-label="Sample vendors">
        {cases.map((c) => (
          <li key={c.case_id}>
            <button
              type="button"
              onClick={() => setSelected(c.case_id)}
              aria-pressed={selected === c.case_id}
              className={cn(
                "w-full rounded-lg border border-l-4 border-l-border bg-card px-3 py-2.5 text-left shadow-card transition-colors hover:bg-muted",
                selected === c.case_id && "border-primary border-l-primary bg-brand-tint ring-1 ring-primary hover:bg-brand-tint",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{c.title}</span>
                <Mono className="text-xs text-muted-foreground">{c.case_id.slice(0, 2)}</Mono>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{c.description}</p>
              <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                Expected: <VendorStatusBadge status={c.expected_status} />
              </div>
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0">
        {!selected ? (
          <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">Choose a sample vendor to see its form and documents.</CardContent></Card>
        ) : detail?.case_id !== selected ? (
          <Loading /> // the previous sample's detail is never shown for a newly selected one
        ) : (
          <Preview detail={detail} onRun={() => onRun(detail.case_id)} running={running} />
        )}
      </div>
    </div>
  )
}
