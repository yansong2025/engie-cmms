"use client"

import type React from "react"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { UploadCloud, FileSpreadsheet, CheckCircle2, Loader2, AlertCircle } from "lucide-react"
import { supabase } from "@/lib/supabaseClient" // Adjust path if your lib is elsewhere

type Status = "idle" | "analyzing" | "done" | "error"

export function AnalyticsUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const canSubmit = file && status !== "analyzing"

  function handleFiles(files: FileList | null) {
    if (files && files.length > 0) {
      setFile(files[0])
      setStatus("idle")
      setErrorMessage(null)
    }
  }

  async function analyze() {
    if (!canSubmit) return

    setStatus("analyzing")
    setErrorMessage(null)

    try {
      // 1. Generate unique file path
      const filePath = `uploads/${Date.now()}_${file.name}`

      // 2. Upload directly to Supabase 'raw-data' bucket
      const { data, error: uploadError } = await supabase.storage
        .from("raw-data")
        .upload(filePath, file, {
          cacheControl: "3600",
          upsert: true,
        })

      if (uploadError) throw uploadError

      console.log("File successfully uploaded to path:", data.path)

      // 3. TODO: Trigger AWS Lambda here
      /*
      const response = await fetch('YOUR_AWS_LAMBDA_URL', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: data.path }),
      });
      
      if (!response.ok) throw new Error("Failed to process file in Lambda");
      
      const result = await response.json();
      console.log('PDF Public URL:', result.report_url);
      */

      setStatus("done")
    } catch (error: any) {
      console.error("Upload process failed:", error)
      setErrorMessage(error.message || "An unknown error occurred during upload.")
      setStatus("error")
    }
  }

  return (
    <section id="analytics" className="w-full py-16 lg:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid items-start gap-10 lg:grid-cols-[1fr_1.1fr]">
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

              <Button size="lg" disabled={!canSubmit} onClick={analyze} className="w-full">
                {status === "analyzing" ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                    Uploading & Analyzing…
                  </>
                ) : (
                  "Analyze"
                )}
              </Button>

              {status === "done" && (
                <div
                  role="status"
                  className="flex items-start gap-2 rounded-md bg-accent px-4 py-3 text-sm text-accent-foreground"
                >
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                  <span>
                    Upload complete. Your detailed report for <strong>{file?.name}</strong> is ready.
                  </span>
                </div>
              )}

              {status === "error" && (
                <div
                  role="alert"
                  className="flex items-start gap-2 rounded-md bg-destructive/15 px-4 py-3 text-sm text-destructive"
                >
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    <strong>Upload failed:</strong> {errorMessage}
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
