import { ArrowRight, ExternalLink } from "lucide-react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { runDocumentUrl, type ExtractedDocument, type RunDetail, type VendorSubmission } from "@/lib/api"
import { DOC_LABELS, MONO_FIELDS, fieldLabel, percent } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Section } from "./Section"

/** Where a document field lives on the submitted form. */
function formValue(field: string, s: VendorSubmission): string | undefined {
  const map: Record<string, string | null | undefined> = {
    legal_name: s.legal_name, pan: s.pan, gstin: s.gstin, ein: s.ein, address: s.address, state: s.state,
    holder_name: s.bank.holder_name, account_number: s.bank.account_number, // already masked by the backend
    ifsc: s.bank.ifsc, routing_number: s.bank.routing_number,
  }
  return map[field] ?? undefined
}

/** Fields the checks flagged on this document (document vs form, or bank holder name). */
function flaggedFields(run: RunDetail, filename: string): Set<string> {
  const flagged = new Set<string>()
  for (const check of run.stages.flatMap((s) => s.checks)) {
    if (check.result === "PASS") continue
    const d = check.details
    if (check.check_id === "DOC_FIELDS_MATCH" && d.filename === filename) {
      for (const m of (d.mismatches as { field: string }[] | undefined) ?? []) flagged.add(m.field)
    }
    if (check.check_id === "BANK_NAME_MATCH" && d.compared === `document:${filename}`) flagged.add("holder_name")
  }
  return flagged
}

function missingFields(run: RunDetail, filename: string): string[] {
  const check = run.stages.flatMap((s) => s.checks)
    .find((c) => c.check_id === "EXTRACTION_CONFIDENCE" && c.details.filename === filename)
  return (check?.details.missing_fields as string[] | undefined) ?? []
}

function DocumentCard({ run, doc }: { run: RunDetail; doc: ExtractedDocument }) {
  const typeMismatch = doc.detected_type !== doc.slot
  const flagged = flaggedFields(run, doc.filename)
  const missing = missingFields(run, doc.filename)
  const minConfidence = run.thresholds.min_field_confidence
  return (
    <div className="overflow-hidden rounded-sm border">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted px-4 py-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-mono text-sm font-semibold">{doc.filename}</span>
          <span className={cn("flex items-center gap-1 text-sm", typeMismatch ? "font-medium text-rejected" : "text-muted-foreground")}>
            Uploaded as {DOC_LABELS[doc.slot]} <ArrowRight className="size-3.5" aria-hidden /> read as {DOC_LABELS[doc.detected_type]}
            {typeMismatch && " (mismatch)"}
          </span>
        </div>
        <a
          href={runDocumentUrl(run.run_id, doc.filename)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
        >
          View PDF <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Field</TableHead>
              <TableHead>On document</TableHead>
              <TableHead>On form</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(doc.fields).map(([field, value]) => {
              const confidence = doc.field_confidence[field] ?? 0
              const low = confidence < minConfidence
              const isFlagged = flagged.has(field)
              const mono = MONO_FIELDS.has(field)
              return (
                <TableRow key={field} className={cn(isFlagged && "bg-rejected-soft")}>
                  <TableCell className="font-medium">{fieldLabel(field)}</TableCell>
                  <TableCell className={cn("whitespace-normal", mono && "font-mono", isFlagged && "text-rejected")}>{value}</TableCell>
                  <TableCell className={cn("whitespace-normal text-muted-foreground", mono && "font-mono")}>
                    {formValue(field, run.submission) ?? "—"}
                  </TableCell>
                  <TableCell className={cn("text-right tabular-nums", low && "font-medium text-pending")}>
                    {percent(confidence)}
                    {low && <span className="sr-only"> (low confidence)</span>}
                    {low && " · low"}
                  </TableCell>
                </TableRow>
              )
            })}
            {missing.map((group) => (
              <TableRow key={group} className="bg-pending-soft">
                <TableCell className="font-medium">{group.split(" or ").map(fieldLabel).join(" or ")}</TableCell>
                <TableCell colSpan={3} className="text-pending">Not found on the document</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {doc.notes.length > 0 && (
        <ul className="border-t px-4 py-2 text-xs text-muted-foreground">
          {doc.notes.map((note) => <li key={note}>Note: {note}</li>)}
        </ul>
      )}
    </div>
  )
}

export function DocumentsPanel({ run }: { run: RunDetail }) {
  return (
    <Section
      title="Documents"
      description="What was read from each file, next to what the vendor typed. Highlighted rows were flagged by a check."
    >
      {run.documents.length === 0 ? (
        <p className="text-sm text-muted-foreground">No documents were read in this run.</p>
      ) : (
        <div className="space-y-4">
          {run.documents.map((doc) => <DocumentCard key={doc.filename} run={run} doc={doc} />)}
        </div>
      )}
    </Section>
  )
}
