import { FilePlus2, RotateCcw, ShieldCheck } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"

import { ErrorBox, Loading, Mono, PageHeader } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useHealth } from "@/hooks/useHealth"
import { api, type Stats, type VendorSummary } from "@/lib/api"
import { relativeTime } from "@/lib/format"

const REFRESH_MS = 5_000

function StatTile({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Card className="py-4">
      <CardContent>
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
        <div className={`mt-1 text-3xl font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
      </CardContent>
    </Card>
  )
}

function ResetDemo({ onDone }: { onDone: () => void }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.resetDemo()
      setConfirming(false)
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!confirming) {
    return (
      <Button variant="outline" onClick={() => setConfirming(true)}>
        <RotateCcw className="size-4" aria-hidden /> Reset demo
      </Button>
    )
  }
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-rejected/30 bg-rejected-soft px-3 py-1.5 text-sm">
      <span className="text-rejected">Delete all vendors, runs and uploads?</span>
      <Button size="sm" variant="destructive" onClick={reset} disabled={busy}>{busy ? "Resetting…" : "Yes, reset"}</Button>
      <Button size="sm" variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancel</Button>
      {error && <span className="text-rejected">{error}</span>}
    </div>
  )
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
        <ShieldCheck className="size-10 text-primary" aria-hidden />
        <h2 className="text-lg font-semibold">No vendors yet</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Each vendor submission is checked in 8 stages (documents, formats, cross-checks and risk), then approved,
          put on hold or rejected, with every reason shown. Try a sample vendor to see it work.
        </p>
        <Button asChild>
          <Link to="/submit"><FilePlus2 className="size-4" aria-hidden /> New submission</Link>
        </Button>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { health } = useHealth()
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)
  const [vendors, setVendors] = useState<VendorSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    Promise.all([api.stats(), api.vendors()]).then(
      ([s, v]) => { setStats(s); setVendors(v); setError(null) },
      (e: Error) => setError(e.message),
    )
  }, [])

  useEffect(load, [load])

  // Keep refreshing while any vendor is still being processed.
  const processing = vendors?.some((v) => v.status === "PROCESSING") ?? false
  useEffect(() => {
    if (!processing) return
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [processing, load])

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Every vendor checked so far, with its latest status."
        actions={
          <>
            {health?.demo_mode && <ResetDemo onDone={load} />}
            <Button asChild><Link to="/submit"><FilePlus2 className="size-4" aria-hidden /> New submission</Link></Button>
          </>
        }
      />
      {error && <ErrorBox title="Could not load the dashboard" message={error} onRetry={load} />}
      {!stats || !vendors ? (
        !error && <Loading />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatTile label="Total vendors" value={stats.total_vendors} />
            <StatTile label="Approved" value={stats.status_counts.APPROVED} tone="text-approved" />
            <StatTile label="Pending" value={stats.status_counts.PENDING} tone="text-pending" />
            <StatTile label="Rejected" value={stats.status_counts.REJECTED} tone="text-rejected" />
            <StatTile label="Total runs" value={stats.total_runs} />
          </div>
          {vendors.length === 0 ? (
            <EmptyState />
          ) : (
            <Card className="py-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Vendor ID</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Country</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Risk</TableHead>
                      <TableHead className="text-right">Runs</TableHead>
                      <TableHead>Last updated</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendors.map((v) => (
                      <TableRow
                        key={v.vendor_id}
                        className="cursor-pointer"
                        onClick={() => navigate(`/vendors/${encodeURIComponent(v.vendor_id)}`)}
                      >
                        <TableCell>
                          <Link to={`/vendors/${encodeURIComponent(v.vendor_id)}`} className="text-primary hover:underline" onClick={(e) => e.stopPropagation()}>
                            <Mono>{v.vendor_id}</Mono>
                          </Link>
                        </TableCell>
                        <TableCell className="font-medium">{v.legal_name}</TableCell>
                        <TableCell>{v.country}</TableCell>
                        <TableCell><VendorStatusBadge status={v.status} /></TableCell>
                        <TableCell className="text-right tabular-nums">{v.risk_score}</TableCell>
                        <TableCell className="text-right tabular-nums">{v.run_count}</TableCell>
                        <TableCell className="text-muted-foreground">{relativeTime(v.updated_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
