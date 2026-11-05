import { ArrowRight, ChevronRight, RefreshCw } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router"

import { ErrorBox, Loading, Mono, PageHeader } from "@/components/PageState"
import { VendorStatusBadge } from "@/components/StatusBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api, type VendorDetail } from "@/lib/api"
import { dateTime, relativeTime } from "@/lib/format"

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{children}</dd>
    </div>
  )
}

export function VendorPage() {
  const { vendorId = "" } = useParams()
  const [vendor, setVendor] = useState<VendorDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api.vendor(vendorId).then((v) => { setVendor(v); setError(null) }, (e: Error) => setError(e.message))
  }, [vendorId])
  useEffect(load, [load])

  if (error) return <ErrorBox title="Could not load this vendor" message={error} onRetry={load} />
  if (!vendor) return <Loading />

  return (
    <div className="space-y-6">
      <PageHeader
        title={vendor.legal_name}
        description={<><Mono>{vendor.vendor_id}</Mono> · {vendor.country === "IN" ? "India" : "USA"}</>}
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
      <Card>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <Fact label="Status"><VendorStatusBadge status={vendor.status} /></Fact>
            <Fact label="Risk score"><span className="tabular-nums">{vendor.risk_score} / 100</span></Fact>
            <Fact label="Runs"><span className="tabular-nums">{vendor.run_count}</span></Fact>
            <Fact label="Bank account">{vendor.account_last4 ? <Mono>••••{vendor.account_last4}</Mono> : "—"}</Fact>
            <Fact label="First submitted">{dateTime(vendor.created_at)}</Fact>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run history</CardTitle>
          {vendor.runs.length > 1 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1 text-sm text-muted-foreground" aria-label="Status over time">
              {vendor.runs.map((r, i) => (
                <span key={r.run_id} className="inline-flex items-center gap-1.5">
                  {i > 0 && <ArrowRight className="size-3.5" aria-hidden />}
                  <VendorStatusBadge status={r.status} />
                </span>
              ))}
            </div>
          )}
        </CardHeader>
        <CardContent>
          {vendor.runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">The first run is still in progress.</p>
          ) : (
            <ol className="divide-y rounded-md border">
              {vendor.runs.map((r) => (
                <li key={r.run_id}>
                  <Link to={`/runs/${r.run_id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/50">
                    <span className="w-14 font-medium">Run {r.run_number}</span>
                    <VendorStatusBadge status={r.status} />
                    <span className="text-sm text-muted-foreground tabular-nums">Risk {r.risk_score}</span>
                    {r.had_errors && <span className="text-xs text-pending">processing error</span>}
                    <span className="ml-auto text-sm text-muted-foreground" title={dateTime(r.started_at)}>
                      {relativeTime(r.started_at)}
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
