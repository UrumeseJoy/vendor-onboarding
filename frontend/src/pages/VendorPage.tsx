import { ArrowRight, ChevronRight, RefreshCw } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"

import { ErrorBox, Loading, Mono, PageHeader } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Fact, Panel } from "@/components/Panel"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, type VendorDetail } from "@/lib/api"
import { dateTime, relativeTime } from "@/lib/format"

export function VendorPage() {
  const { vendorId = "" } = useParams()
  const navigate = useNavigate()
  const [vendor, setVendor] = useState<VendorDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api.vendor(vendorId).then((v) => { setVendor(v); setError(null) }, (e: Error) => setError(e.message))
  }, [vendorId])
  useEffect(load, [load])

  if (error) return <ErrorBox title="Could not load this vendor" message={error} onRetry={load} />
  if (!vendor) return <Loading />

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumb={[{ label: "Vendors", to: "/" }, { label: vendor.vendor_id }]}
        title={vendor.legal_name}
        description={<><Mono className="text-foreground">{vendor.vendor_id}</Mono> · {vendor.country === "IN" ? "India" : "USA"}</>}
        actions={
          vendor.status === "PENDING" && (
            <Button asChild>
              <Link to={`/submit?resubmit=${encodeURIComponent(vendor.vendor_id)}`}>
                <RefreshCw className="size-4" aria-hidden /> Resubmit for this vendor
              </Link>
            </Button>
          )
        }
      />
      <section className="overflow-hidden rounded-sm border bg-card">
        <dl className="grid grid-cols-2 divide-x divide-y sm:grid-cols-5 sm:divide-y-0 [&>div]:px-4 [&>div]:py-2.5">
          <Fact label="Status"><VendorStatusBadge status={vendor.status} /></Fact>
          <Fact label="Risk score"><span className="tabular-nums">{vendor.risk_score} / 100</span></Fact>
          <Fact label="Runs"><span className="tabular-nums">{vendor.run_count}</span></Fact>
          <Fact label="Bank account">{vendor.account_last4 ? <Mono>••••{vendor.account_last4}</Mono> : "—"}</Fact>
          <Fact label="First submitted">{dateTime(vendor.created_at)}</Fact>
        </dl>
      </section>

      <Panel
        title="Run history"
        flush
        action={vendor.runs.length > 1 && (
          <div className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground" aria-label="Status over time">
            {vendor.runs.map((r, i) => (
              <span key={r.run_id} className="inline-flex items-center gap-1.5">
                {i > 0 && <ArrowRight className="size-3.5" aria-hidden />}
                <VendorStatusBadge status={r.status} />
              </span>
            ))}
          </div>
        )}
      >
        {vendor.runs.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">
            {vendor.status === "PROCESSING"
              ? "The first run is still in progress."
              : "No run was saved for this vendor: processing was interrupted. A person needs to review it."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Risk</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead className="w-8"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vendor.runs.map((r) => (
                  <TableRow key={r.run_id} className="cursor-pointer" onClick={() => navigate(`/runs/${r.run_id}`)}>
                    <TableCell>
                      <Link to={`/runs/${r.run_id}`} className="font-semibold hover:underline" onClick={(e) => e.stopPropagation()}>
                        Run {r.run_number}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-2">
                        <VendorStatusBadge status={r.status} />
                        {r.had_errors && <span className="text-xs text-pending">processing error</span>}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{r.risk_score}</TableCell>
                    <TableCell className="text-muted-foreground" title={dateTime(r.started_at)}>{relativeTime(r.started_at)}</TableCell>
                    <TableCell className="text-muted-foreground"><ChevronRight className="size-4" aria-hidden /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
    </div>
  )
}
