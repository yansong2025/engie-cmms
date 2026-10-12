"use client"

import type React from "react"
import { useEffect, useRef, useState } from "react"
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

type AnalysisResult = {
  metrics: {
    period_start: string
    period_end: string
    total_kwh: number
    est_cost: number
    est_co2_kg: number
    peak_kwh: number
    peak_at: string
    base_load_kwh: number
    load_factor_pct: number
    anomaly_events_high: number
    anomaly_events_low: number
    anomaly_excess_kwh: number
  }
  quality: {
    rows_read: number
    rows_used: number
    missing_intervals: number
  }
  events: {
    start: string
    duration_minutes: number
    direction: "high" | "low"
    excess_kwh: number
  }[]
  day_profiles: {
    profiles: { label: string; days: number; description: string; avg_daily_kwh: number }[]
    unusual_days: { date: string; day: string; reason: string; main_difference: string }[]
  } | null
  notes: string[]
  pdf_base64: string
}

const MAX_LISTED = 3

// Keep in sync with MAX_FILE_BYTES in api/analyze.py.
const MAX_FILE_BYTES = 4 * 1024 * 1024
const ACCEPTED_EXTENSIONS = [".csv", ".xlsx"]
const DEFAULT_TARIFF = "0.15"
const DEFAULT_EMISSION_FACTOR = "0.4"

const numberFormat = new Intl.NumberFormat("en", { maximumFractionDigits: 1 })

function formatDuration(minutes: number) {
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return hours ? `${hours} h ${mins.toString().padStart(2, "0")} min` : `${mins} min`
}

function validateFile(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return "Unsupported file type. Please choose a .csv or .xlsx file."
  }
  if (file.size > MAX_FILE_BYTES) {
    return `This file is ${(file.size / 1024 / 1024).toFixed(1)} MB. The limit is 4 MB — try exporting a shorter period.`
  }
  return null
}

function isValidRate(value: string) {
  return value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0
}

async function readError(response: Response): Promise<string> {
  // Platform-level failures (size limit, timeout) are not JSON.
  if (response.status === 413) return "File is too large. The limit is 4 MB."
  if (response.status === 504) return "The analysis timed out. Try a smaller file."
  try {
    const data = await response.json()
    if (typeof data.detail === "string") return data.detail
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg
  } catch {
    // fall through to the generic message
  }
  return `The server could not process the file (error ${response.status}).`
}

function pdfBlobUrl(base64: string) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
  return URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }))
}

export function AnalyticsUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [tariff, setTariff] = useState(DEFAULT_TARIFF)
  const [emissionFactor, setEmissionFactor] = useState(DEFAULT_EMISSION_FACTOR)
  const [status, setStatus] = useState<Status>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const ratesValid = isValidRate(tariff) && isValidRate(emissionFactor)
  const canSubmit = file && ratesValid && status !== "analyzing"

  // Release the previous report's blob when it is replaced or the page unmounts.
  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    }
  }, [pdfUrl])

  function reset() {
    setStatus("idle")
    setErrorMessage(null)
    setResult(null)
    setPdfUrl(null)
  }

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    reset()

    const problem = validateFile(files[0])
    if (problem) {
      setFile(null)
      setErrorMessage(problem)
      setStatus("error")
      return
    }
    setFile(files[0])
  }

  async function analyze() {
    if (!file || !canSubmit) return

    reset()
    setStatus("analyzing")

    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("tariff", tariff)
      formData.append("emission_factor", emissionFactor)

      const response = await fetch("/api/analyze", { method: "POST", body: formData })
      if (!response.ok) {
        throw new Error(await readError(response))
      }

      const data: AnalysisResult = await response.json()
      setResult(data)
      setPdfUrl(pdfBlobUrl(data.pdf_base64))
      setStatus("done")
    } catch (error) {
      console.error("Analysis process failed:", error)
      setErrorMessage(
        error instanceof Error ? error.message : "An unknown error occurred during analysis.",
      )
      setStatus("error")
    }
  }

  const reportName = file ? `report_${file.name.replace(/\.[^.]+$/, "")}.pdf` : "report.pdf"
  const inputClass =
    "h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive"

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
              Upload a utility file. Get insight in seconds.
            </h2>
            <p className="max-w-md text-pretty leading-relaxed text-muted-foreground">
              Drop in an interval meter export. ENGIE Digital FM checks the data, profiles
              consumption by day and hour, and flags unusual readings — then gives you a PDF report.
            </p>
            <ul className="mt-2 flex flex-col gap-3 text-sm text-muted-foreground">
              {[
                "Supports CSV and XLSX meter exports",
                "Cost and carbon estimates at your own rates",
                "Anomaly detection against typical time-of-week usage",
                "Files are analysed in memory and never stored",
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
                      <span className="text-xs text-muted-foreground">
                        CSV or XLSX up to 4 MB, with a date/time column and a consumption (kWh) column
                      </span>
                    </>
                  )}
                  <input
                    ref={inputRef}
                    id="file"
                    type="file"
                    accept={ACCEPTED_EXTENSIONS.join(",")}
                    className="sr-only"
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => {
                      handleFiles(e.target.files)
                      e.target.value = "" // allow re-selecting the same file
                    }}
                  />
                </div>
              </div>

              {/* Rates */}
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-2 text-sm font-medium text-foreground">
                  Tariff (cost per kWh)
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.01"
                    value={tariff}
                    aria-invalid={!isValidRate(tariff)}
                    onChange={(e) => setTariff(e.target.value)}
                    className={inputClass}
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm font-medium text-foreground">
                  Emission factor (kg CO₂e per kWh)
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.01"
                    value={emissionFactor}
                    aria-invalid={!isValidRate(emissionFactor)}
                    onChange={(e) => setEmissionFactor(e.target.value)}
                    className={inputClass}
                  />
                </label>
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

              {/* Results */}
              {status === "done" && result && (
                <div
                  role="status"
                  className="flex flex-col gap-4 rounded-md bg-accent p-4 text-sm text-accent-foreground"
                >
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    <span>
                      Analysis complete for <strong>{file?.name}</strong>,{" "}
                      {result.metrics.period_start.slice(0, 10)} to{" "}
                      {result.metrics.period_end.slice(0, 10)}.
                    </span>
                  </div>

                  <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {[
                      ["Total consumption", `${numberFormat.format(result.metrics.total_kwh)} kWh`],
                      ["Estimated cost", numberFormat.format(result.metrics.est_cost)],
                      ["Carbon", `${numberFormat.format(result.metrics.est_co2_kg)} kg CO₂e`],
                      ["Peak reading", `${numberFormat.format(result.metrics.peak_kwh)} kWh`],
                      ["Load factor", `${numberFormat.format(result.metrics.load_factor_pct)}%`],
                      [
                        "Anomaly events",
                        `${result.metrics.anomaly_events_high} high · ${result.metrics.anomaly_events_low} low`,
                      ],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md bg-background/70 p-3">
                        <dt className="text-xs text-muted-foreground">{label}</dt>
                        <dd className="mt-1 font-semibold tabular-nums text-foreground">{value}</dd>
                      </div>
                    ))}
                  </dl>

                  {result.events.length > 0 && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs font-semibold text-foreground">
                        Largest anomaly events
                      </span>
                      <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                        {result.events.slice(0, MAX_LISTED).map((event) => (
                          <li key={event.start} className="tabular-nums">
                            {event.start.slice(0, 16).replace("T", " ")} ·{" "}
                            {formatDuration(event.duration_minutes)} ·{" "}
                            {event.excess_kwh > 0 ? "+" : ""}
                            {numberFormat.format(event.excess_kwh)} kWh vs typical
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.day_profiles && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs font-semibold text-foreground">
                        Typical days: {result.day_profiles.profiles.length} profile(s),{" "}
                        {result.day_profiles.unusual_days.length} unusual day(s)
                      </span>
                      <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                        {result.day_profiles.profiles.map((profile) => (
                          <li key={profile.label}>
                            Profile {profile.label}: {profile.days} days, {profile.description}, avg{" "}
                            {numberFormat.format(profile.avg_daily_kwh)} kWh/day
                          </li>
                        ))}
                        {result.day_profiles.unusual_days.slice(0, MAX_LISTED).map((day) => (
                          <li key={day.date}>
                            Unusual: {day.date} ({day.day}) — {day.reason.toLowerCase()},{" "}
                            {day.main_difference}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.notes.length > 0 && (
                    <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                      {result.notes.map((note) => (
                        <li key={note} className="flex items-start gap-1.5">
                          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          {note}
                        </li>
                      ))}
                    </ul>
                  )}

                  {pdfUrl && (
                    <a
                      href={pdfUrl}
                      download={reportName}
                      className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow transition-colors hover:bg-primary/90"
                    >
                      <Download className="h-3.5 w-3.5" aria-hidden="true" />
                      Download PDF Report
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
                  <span>{errorMessage}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
