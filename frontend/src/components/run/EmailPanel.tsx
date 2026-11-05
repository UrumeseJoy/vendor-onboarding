import { CircleCheck, Mail, Pencil, Sparkles } from "lucide-react"
import { useState } from "react"

import { ErrorBox } from "@/components/PageState"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { api, type VendorEmail } from "@/lib/api"
import { dateTime } from "@/lib/format"
import { Section } from "./Section"

export function EmailPanel({ runId, email, onChange }: {
  runId: string; email: VendorEmail; onChange: (email: VendorEmail) => void
}) {
  const [editing, setEditing] = useState(false)
  const [subject, setSubject] = useState(email.subject)
  const [body, setBody] = useState(email.body)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sent = email.status === "SENT"

  const approve = async () => {
    setSaving(true)
    setError(null)
    try {
      const edits = editing ? { subject, body } : undefined
      onChange(await api.approveEmail(runId, edits))
      setEditing(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const label = email.generated_by === "ai"
    ? <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs"><Sparkles className="size-3" aria-hidden /> AI draft</span>
    : <span className="rounded-full border px-2 py-0.5 text-xs">Template</span>

  return (
    <Section
      title="Vendor email"
      icon={<Mail className="size-4" />}
      description="Drafted for a person to check. Approving only marks it as sent: nothing is actually emailed."
      action={label}
    >
      {sent ? (
        <p className="mb-3 flex items-center gap-2 rounded-md bg-approved-soft px-3 py-2 text-sm text-approved">
          <CircleCheck className="size-4" aria-hidden />
          Approved and marked as sent {dateTime(email.approved_at)}{email.edited && " (edited before sending)"}.
        </p>
      ) : email.fallback_reason ? (
        <p className="mb-3 text-xs text-muted-foreground">Template used because {email.fallback_reason}.</p>
      ) : null}

      {editing ? (
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="email-subject">Subject</Label>
            <Input id="email-subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email-body">Body</Label>
            <Textarea id="email-body" rows={12} value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
        </div>
      ) : (
        <div className="rounded-md border bg-muted/30 p-4">
          <p className="font-medium">{email.subject}</p>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{email.body}</p>
        </div>
      )}

      {error && <ErrorBox title="Could not approve the email" message={error} />}

      {!sent && (
        <div className="mt-4 flex flex-wrap gap-2">
          {editing ? (
            <Button variant="outline" onClick={() => { setEditing(false); setSubject(email.subject); setBody(email.body) }}>
              Cancel edits
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="size-4" aria-hidden /> Edit
            </Button>
          )}
          <Button onClick={approve} disabled={saving || (editing && (!subject.trim() || !body.trim()))}>
            <CircleCheck className="size-4" aria-hidden /> {saving ? "Approving…" : "Approve & mark as sent"}
          </Button>
        </div>
      )}
    </Section>
  )
}
