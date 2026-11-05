import { ChevronRight, FilePlus2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"

import { ErrorBox, Loading, Mono, PageHeader } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Panel } from "@/components/Panel"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, type Stats, type VendorSummary } from "@/lib/api"
import { relativeTime } from "@/lib/format"

const REFRESH_MS = 5_000

function SummaryCell({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="px-4 py-3">
      <div className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{label}</div>
      <div className={`mt-1 text-[28px] leading-9 font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  )
}

function EmptyState() {
  return (
    <Panel>
      <div className="flex flex-col items-start gap-3 py-4">
        <h2 className="text-[15px] font-semibold">No vendors yet</h2>
        <p className="max-w-xl text-sm text-muted-foreground">
          Each vendor submission is checked in 8 stages (documents, formats, cross-checks and risk), then approved,
          put on hold or rejected, with every reason shown. Try a sample vendor to see it work.
        </p>
        <Button asChild>
          <Link to="/submit"><FilePlus2 className="size-4" aria-hidden /> New submission</Link>
        </Button>
      </div>
    </Panel>
  )
}

export function DashboardPage() {
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
        breadcrumb={[{ label: "Vendors" }]}
        title="Dashboard"
        description="Every vendor checked so far, with its latest status."
        actions={<Button asChild><Link to="/submit"><FilePlus2 className="size-4" aria-hidden /> New submission</Link></Button>}
      />
      {error && <ErrorBox title="Could not load the dashboard" message={error} onRetry={load} />}
      {!stats || !vendors ? (
        !error && <Loading />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 divide-x divide-y overflow-hidden rounded-sm border bg-card sm:grid-cols-5 sm:divide-y-0">
            <SummaryCell label="Total vendors" value={stats.total_vendors} />
            <SummaryCell label="Approved" value={stats.status_counts.APPROVED} tone="text-approved" />
            <SummaryCell label="Pending" value={stats.status_counts.PENDING} tone="text-pending" />
            <SummaryCell label="Rejected" value={stats.status_counts.REJECTED} tone="text-rejected" />
            <SummaryCell label="Total runs" value={stats.total_runs} />
          </div>
          {vendors.length === 0 ? (
            <EmptyState />
          ) : (
            <Panel title="Vendors" flush>
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
                      <TableHead className="w-8"><span className="sr-only">Open</span></TableHead>
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
                          <Link to={`/vendors/${encodeURIComponent(v.vendor_id)}`} className="text-foreground hover:underline" onClick={(e) => e.stopPropagation()}>
                            <Mono>{v.vendor_id}</Mono>
                          </Link>
                        </TableCell>
                        <TableCell className="font-medium">{v.legal_name}</TableCell>
                        <TableCell>{v.country}</TableCell>
                        <TableCell><VendorStatusBadge status={v.status} /></TableCell>
                        <TableCell className="text-right tabular-nums">{v.risk_score}</TableCell>
                        <TableCell className="text-right tabular-nums">{v.run_count}</TableCell>
                        <TableCell className="text-muted-foreground">{relativeTime(v.updated_at)}</TableCell>
                        <TableCell className="text-muted-foreground"><ChevronRight className="size-4" aria-hidden /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Panel>
          )}
        </div>
      )}
    </div>
  )
}
