import { Send } from "lucide-react"
import { useState, type FormEvent, type ReactNode } from "react"

import { ErrorBox } from "@/components/PageState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Country, DocType, VendorSubmission } from "@/lib/api"
import { DOC_LABELS } from "@/lib/format"
import { FileDrop } from "./FileDrop"

interface Slot {
  key: string
  label: string
  options: DocType[] // the vendor picks one when there is a choice (cheque or bank letter)
}

const SLOTS: Record<Country, Slot[]> = {
  IN: [
    { key: "gst", label: "GST certificate", options: ["GST_CERTIFICATE"] },
    { key: "pan", label: "PAN card", options: ["PAN_CARD"] },
    { key: "bank", label: "Cancelled cheque or bank letter", options: ["CANCELLED_CHEQUE", "BANK_LETTER"] },
  ],
  US: [
    { key: "w9", label: "Form W-9", options: ["W9_FORM"] },
    { key: "bank", label: "Bank letter", options: ["BANK_LETTER"] },
  ],
}

const EMPTY = {
  legal_name: "", state: "", address: "", contact_email: "", pan: "", gstin: "", ein: "",
  holder_name: "", account_number: "", ifsc: "", routing_number: "",
}
type Fields = typeof EMPTY

function TextField({ id, label, value, onChange, required, mono, type = "text", hint }: {
  id: keyof Fields; label: string; value: string; onChange: (id: keyof Fields, v: string) => void
  required?: boolean; mono?: boolean; type?: string; hint?: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}{required && <span className="text-rejected"> *</span>}</Label>
      <Input id={id} type={type} value={value} required={required} className={mono ? "font-mono" : ""}
        onChange={(e) => onChange(id, e.target.value)} autoComplete="off" />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function UploadForm({ onSubmit, busy, serverError }: {
  onSubmit: (submission: VendorSubmission, files: File[]) => void; busy: boolean; serverError: string | null
}) {
  const [country, setCountry] = useState<Country>("IN")
  const [bankCountry, setBankCountry] = useState<Country>("IN")
  const [fields, setFields] = useState<Fields>(EMPTY)
  const [files, setFiles] = useState<Record<string, File | null>>({})
  const [bankDocType, setBankDocType] = useState<DocType>("CANCELLED_CHEQUE")
  const [problem, setProblem] = useState<string | null>(null)

  const set = (id: keyof Fields, value: string) => setFields((f) => ({ ...f, [id]: value }))
  const india = country === "IN"

  const changeCountry = (value: Country) => {
    setCountry(value)
    setBankCountry(value)
    setFiles({})
    setBankDocType(value === "IN" ? "CANCELLED_CHEQUE" : "BANK_LETTER")
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const chosen = SLOTS[country]
      .map((slot) => ({ slot, file: files[slot.key] }))
      .filter((x): x is { slot: Slot; file: File } => Boolean(x.file))
    const names = chosen.map((x) => x.file.name)
    if (new Set(names).size !== names.length) {
      setProblem("Each uploaded file needs a different file name.")
      return
    }
    setProblem(null)
    const submission: VendorSubmission = {
      legal_name: fields.legal_name,
      country,
      state: fields.state,
      address: fields.address,
      contact_email: fields.contact_email,
      pan: india ? fields.pan || null : null,
      gstin: india ? fields.gstin || null : null,
      ein: india ? null : fields.ein || null,
      bank: {
        holder_name: fields.holder_name,
        account_number: fields.account_number,
        ifsc: india ? fields.ifsc || null : null,
        routing_number: india ? null : fields.routing_number || null,
        bank_country: bankCountry,
      },
      documents: chosen.map(({ slot, file }) => ({
        slot: slot.options.length > 1 ? bankDocType : slot.options[0],
        filename: file.name,
      })),
    }
    onSubmit(submission, chosen.map((x) => x.file))
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <Card>
        <CardHeader><CardTitle className="text-base">Company</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="country">Country</Label>
            <Select value={country} onValueChange={(v) => changeCountry(v as Country)}>
              <SelectTrigger id="country" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="IN">India</SelectItem>
                <SelectItem value="US">USA</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <TextField id="legal_name" label="Legal name" value={fields.legal_name} onChange={set} required />
          <TextField id="contact_email" label="Contact email" type="email" value={fields.contact_email} onChange={set} required />
          <TextField id="state" label="State" value={fields.state} onChange={set} required />
          <div className="sm:col-span-2">
            <TextField id="address" label="Address" value={fields.address} onChange={set} required />
          </div>
          {india ? (
            <>
              <TextField id="pan" label="PAN" value={fields.pan} onChange={set} mono hint="10 characters, like AABCS1234K" />
              <TextField id="gstin" label="GSTIN" value={fields.gstin} onChange={set} mono hint="15 characters, like 33AABCS1234K1ZN" />
            </>
          ) : (
            <TextField id="ein" label="EIN" value={fields.ein} onChange={set} mono hint="Like 84-1234567" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Bank account</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <TextField id="holder_name" label="Account holder name" value={fields.holder_name} onChange={set} required />
          <TextField id="account_number" label="Account number" value={fields.account_number} onChange={set} required mono
            hint="Only the last 4 digits are ever shown after submission." />
          {india ? (
            <TextField id="ifsc" label="IFSC" value={fields.ifsc} onChange={set} mono hint="Like HDFC0001234" />
          ) : (
            <TextField id="routing_number" label="Routing number" value={fields.routing_number} onChange={set} mono hint="9 digits" />
          )}
          <div className="space-y-1.5">
            <Label htmlFor="bank_country">Bank country</Label>
            <Select value={bankCountry} onValueChange={(v) => setBankCountry(v as Country)}>
              <SelectTrigger id="bank_country" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="IN">India</SelectItem>
                <SelectItem value="US">USA</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Documents</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SLOTS[country].map((slot) => (
            <div key={slot.key} className="space-y-2">
              <FileDrop id={`file-${slot.key}`} label={slot.label} file={files[slot.key] ?? null}
                onChange={(file) => setFiles((f) => ({ ...f, [slot.key]: file }))} />
              {slot.options.length > 1 && (
                <Select value={bankDocType} onValueChange={(v) => setBankDocType(v as DocType)}>
                  <SelectTrigger className="w-full" aria-label="Type of bank document"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {slot.options.map((o) => <SelectItem key={o} value={o}>{DOC_LABELS[o]}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {(problem || serverError) && (
        <ErrorBox title="The submission was not accepted" message={problem ?? serverError ?? ""} />
      )}
      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>
          <Send className="size-4" aria-hidden /> {busy ? "Submitting…" : "Submit for checking"}
        </Button>
      </div>
    </form>
  )
}
