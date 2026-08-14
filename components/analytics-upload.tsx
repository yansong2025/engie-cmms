"use client"

import type React from "react"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Download,
} from "lucide-react"

type Status = "idle" | "analyzing" | "done" | "error"

export function AnalyticsUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const canSubmit = file && status !== "analyzing"

  function handleFiles(files: FileList | null) {
    if (files && files.length > 0) {
      setFile(files[0])
      setStatus("idle")
      setErrorMessage(null)
      setPdfUrl(null)
    }
  }

  async function analyze() {
    if (!file || !canSubmit) return

    setStatus("analyzing")
    setErrorMessage(null)
    setPdfUrl(null)

    try {
      // 1. Package file directly into FormData
      const formData = new FormData()
      formData.append("file", file)

      // 2. Post directly to your Vercel Python function (/api/analyze)
      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData, // Browser automatically configures multipart/form-data headers
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Failed to process utility file")
      }

      if (!data.pdf_url) {
        throw new Error("Report generated, but no download URL was returned.")
      }

      // 3. Save PDF URL & trigger auto-download in new tab
      setPdfUrl(data.pdf_url)
      setStatus("done")
      window.open(data.pdf_url, "_blank")
    } catch (error: any) {
      console.error("Analysis process failed:", error)
      setErrorMessage(error.message || "An unknown error occurred during analysis.")
      setStatus("error")
    }
  }

  return (
    <section id="analytics" className="w-full py-16 lg:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid items-start gap-10 lg:grid-cols-[1fr_1.1fr]">
          {/* Left Hero Description */}
          <div className="flex flex-col gap-4">
            <span className="text-sm font-semibold uppercase tracking-wider text-primary">
              CMMS Utility Analytics
            </span>
            <h2 className="text-pretty text-3xl font-bold tracking-tight sm:text-4xl">
              Upload a utility file. Get insight in minutes.
            </h2>
            <p className="max-w-md text-pretty leading-relaxed text-muted-foreground">
              Drop in your meter exports or CMMS utility report. ENGIE Digital FM normalizes the data,
              benchmarks consumption, and flags anomalies — then shows your results in minutes.
            </p>
            <ul className="mt-2 flex flex-col gap-3 text-sm text-muted-foreground">
              {[
                "Supports CSV, XLSX and CMMS exports",
                "Automatic consumption benchmarking",
                "Anomaly and cost-spike detection",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Right Upload Box */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm sm:p-8">
            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-2">
                <span className="text-sm font-medium text-foreground">Utility file</span>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => inputRef.current?.click()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      inputRef.current?.click()
                    }
                  }}
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragging(true)
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault()
                    setDragging(false)
                    handleFiles(e.dataTransfer.files)
                  }}
                  className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed px-4 py-8 text-center transition-colors ${
                    dragging ? "border-primary bg-accent" : "border-input bg-background hover:bg-secondary/60"
                  }`}
                >
                  {file ? (
                    <>
                      <FileSpreadsheet className="h-7 w-7 text-primary" aria-hidden="true" />
                      <span className="text-sm font-medium text-foreground">{file.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {(file.size / 1024).toFixed(0)} KB · click to replace
                      </span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
                      <span className="text-sm font-medium text-foreground">
                        Drop your file here or click to browse
                      </span>
                      <span className="text-xs text-muted-foreground">CSV or XLSX up to 25 MB</span>
                    </>
                  )}
                  <input
                    ref={inputRef}
                    id="file"
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    className="sr-only"
                    onChange={(e) => handleFiles(e.target.files)}
                  />
                </div>
              </div>

              {/* Action Button */}
              <Button size="lg" disabled={!canSubmit} onClick={analyze} className="w-full">
                {status === "analyzing" ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    Analyzing Data & Generating Report…
                  </>
                ) : (
                  "Analyze & Generate PDF"
                )}
              </Button>

              {/* Success Banner */}
              {status === "done" && (
                <div
                  role="status"
                  className="flex flex-col gap-3 rounded-md bg-accent p-4 text-sm text-accent-foreground"
                >
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    <span>
                      Analysis complete! Your report for <strong>{file?.name}</strong> is ready.
                    </span>
                  </div>

                  {pdfUrl && (
                    <a
                      href={pdfUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow transition-colors hover:bg-primary/90"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Open PDF Report
                    </a>
                  )}
                </div>
              )}

              {/* Error Banner */}
              {status === "error" && (
                <div
                  role="alert"
                  className="flex items-start gap-2 rounded-md bg-destructive/15 px-4 py-3 text-sm text-destructive"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    <strong>Analysis failed:</strong> {errorMessage}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}