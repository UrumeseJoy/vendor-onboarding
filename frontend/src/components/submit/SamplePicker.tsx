import { ExternalLink, Play } from "lucide-react"
import { useEffect, useState } from "react"

import { ErrorBox, Loading, Mono } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/Panel"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { absoluteUrl, api, type DemoCase, type DemoCaseDetail } from "@/lib/api"
import { DOC_LABELS } from "@/lib/format"
import { cn } from "@/lib/utils"

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div className="flex gap-3 border-b px-4 py-2 text-sm">
      <dt className="w-32 shrink-0 text-[11px] leading-5 font-semibold tracking-wider text-muted-foreground uppercase">{label}</dt>
      <dd className={cn("min-w-0 break-words", mono && "font-mono", !value && "text-muted-foreground")}>{value || "—"}</dd>
    </div>
  )
}

function Preview({ detail, onRun, running }: { detail: DemoCaseDetail; onRun: () => void; running: boolean }) {
  const s = detail.submission
  const india = s.country === "IN"
  return (
    <Panel
      title={s.legal_name}
      description={detail.description}
      flush
    >
      <dl className="grid sm:grid-cols-2 sm:[&>div:nth-child(odd)]:border-r">
        <Field label="Country" value={india ? "India" : "USA"} />
        <Field label="State" value={s.state} />
        <Field label="Contact email" value={s.contact_email} />
        {india ? <Field label="PAN" value={s.pan} mono /> : <Field label="EIN" value={s.ein} mono />}
        {india && <Field label="GSTIN" value={s.gstin} mono />}
        <Field label="Account holder" value={s.bank.holder_name} />
        <Field label="Account number" value={s.bank.account_number} mono />
        <Field label={india ? "IFSC" : "Routing no."} value={india ? s.bank.ifsc : s.bank.routing_number} mono />
        <div className="sm:col-span-2"><Field label="Address" value={s.address} /></div>
      </dl>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File name</TableHead>
              <TableHead>Claimed type</TableHead>
              <TableHead className="text-right">Document</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {detail.documents.map((d) => (
              <TableRow key={d.filename}>
                <TableCell><Mono>{d.filename}</Mono></TableCell>
                <TableCell>{DOC_LABELS[d.slot]}</TableCell>
                <TableCell className="text-right">
                  <a
                    href={absoluteUrl(d.file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-brand hover:underline"
                  >
                    View <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-end border-t bg-muted px-4 py-3">
        <Button onClick={onRun} disabled={running}>
          <Play className="size-4" aria-hidden /> {running ? "Starting…" : "Run this sample"}
        </Button>
      </div>
    </Panel>
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
    <div className="grid gap-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
      <ul className="divide-y self-start overflow-hidden rounded-sm border bg-card" aria-label="Sample vendors">
        {cases.map((c) => (
          <li key={c.case_id}>
            <button
              type="button"
              onClick={() => setSelected(c.case_id)}
              aria-pressed={selected === c.case_id}
              className={cn(
                "grid w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] items-start gap-x-3 border-l-[3px] border-l-transparent px-3 py-2.5 text-left transition-colors hover:bg-muted",
                selected === c.case_id && "border-l-primary bg-brand-tint hover:bg-brand-tint",
              )}
            >
              <Mono className="pt-px text-xs text-muted-foreground">{c.case_id.slice(0, 2)}</Mono>
              <span className="min-w-0">
                <span className="block font-semibold">{c.title}</span>
                <span className="block truncate text-xs text-muted-foreground" title={c.description}>{c.description}</span>
              </span>
              <VendorStatusBadge status={c.expected_status} />
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0">
        {!selected ? (
          <Panel><p className="py-6 text-center text-sm text-muted-foreground">Choose a sample vendor to see its form and documents.</p></Panel>
        ) : detail?.case_id !== selected ? (
          <Loading /> // the previous sample's detail is never shown for a newly selected one
        ) : (
          <Preview detail={detail} onRun={() => onRun(detail.case_id)} running={running} />
        )}
      </div>
    </div>
  )
}
