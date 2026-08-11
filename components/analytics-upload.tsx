"use client"

import type React from "react"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { UploadCloud, FileSpreadsheet, CheckCircle2, Loader2 } from "lucide-react"

type Status = "idle" | "analyzing" | "done"

export function AnalyticsUpload() {
  const [email, setEmail] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<Status>("idle")
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  const canSubmit = emailValid && file && status !== "analyzing"

  function handleFiles(files: FileList | null) {
    if (files && files.length > 0) {
      setFile(files[0])
      setStatus("idle")
    }
  }

  function analyze() {
    if (!canSubmit) return
    setStatus("analyzing")
    // Simulated processing — wire this to your CMMS analytics endpoint.
    setTimeout(() => setStatus("done"), 1800)
  }

  return (
    <section id="analytics" className="border-b border-border bg-secondary/40 py-16 lg:py-24">
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
              benchmarks consumption, and flags anomalies — then sends your results straight to your inbox.
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
                <label htmlFor="email" className="text-sm font-medium text-foreground">
                  Work email
                </label>
                <input
                  id="email"
                  type="email"
                  inputMode="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 rounded-md border border-input bg-background px-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/40"
                />
              </div>

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
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Analyzing…
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
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    Analysis complete. A detailed report for <strong>{file?.name}</strong> is on its way to{" "}
                    <strong>{email}</strong>.
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
