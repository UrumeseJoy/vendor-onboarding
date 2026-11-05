import { RefreshCw } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"

import { ErrorBox, Mono, PageHeader } from "@/components/PageState"
import { SamplePicker } from "@/components/submit/SamplePicker"
import { UploadForm } from "@/components/submit/UploadForm"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, type Started, type VendorSubmission } from "@/lib/api"

export function SubmitPage() {
  const [params] = useSearchParams()
  const resubmitFor = params.get("resubmit") ?? undefined
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [sampleError, setSampleError] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const start = async (call: () => Promise<Started>, setError: (m: string | null) => void) => {
    setBusy(true)
    setError(null)
    try {
      const { run_id } = await call()
      navigate(`/runs/${run_id}`)
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  const runSample = (caseId: string) => start(() => api.runDemoCase(caseId, resubmitFor), setSampleError)
  const upload = (submission: VendorSubmission, files: File[]) =>
    start(() => api.submit(submission, files, resubmitFor), setUploadError)

  return (
    <div>
      <PageHeader
        title={resubmitFor ? "Resubmit documents" : "New submission"}
        description="Run a ready-made sample vendor, or fill in the form and upload PDFs yourself."
      />
      {resubmitFor && (
        <div className="mb-6 flex flex-wrap items-center gap-2 rounded-md border border-processing/30 bg-processing-soft px-4 py-3 text-sm text-processing">
          <RefreshCw className="size-4" aria-hidden />
          <span>
            Resubmitting for <Mono>{resubmitFor}</Mono>. The new run is added to this vendor's history.
            For sample 04, choose sample 05 (the corrected documents).
          </span>
          <Link to="/submit" className="ml-auto font-medium underline-offset-4 hover:underline">Cancel</Link>
        </div>
      )}
      <Tabs defaultValue="sample">
        <TabsList className="mb-4">
          <TabsTrigger value="sample">Load sample vendor</TabsTrigger>
          <TabsTrigger value="upload">Upload your own</TabsTrigger>
        </TabsList>
        <TabsContent value="sample">
          {sampleError && <ErrorBox title="Could not start the run" message={sampleError} />}
          <SamplePicker onRun={runSample} running={busy} />
        </TabsContent>
        <TabsContent value="upload">
          <UploadForm onSubmit={upload} busy={busy} serverError={uploadError} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
