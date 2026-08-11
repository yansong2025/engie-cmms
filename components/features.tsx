import { Gauge, Wrench, Leaf, LineChart, ShieldCheck, Building2 } from "lucide-react"

const features = [
  {
    icon: Gauge,
    title: "Energy & utility monitoring",
    desc: "Track consumption across every meter and site in real time, with automatic benchmarking against targets.",
  },
  {
    icon: Wrench,
    title: "Connected CMMS",
    desc: "Plan preventive maintenance, manage work orders, and keep asset histories in a single source of truth.",
  },
  {
    icon: Leaf,
    title: "Sustainability reporting",
    desc: "Turn raw data into audit-ready carbon and ESG reports aligned with your net-zero commitments.",
  },
  {
    icon: LineChart,
    title: "Predictive insight",
    desc: "Spot anomalies and cost spikes before they escalate, with forecasting built on your historical data.",
  },
  {
    icon: ShieldCheck,
    title: "Compliance & safety",
    desc: "Stay ahead of regulations with automated checks, alerts, and a full digital audit trail.",
  },
  {
    icon: Building2,
    title: "Portfolio overview",
    desc: "See the health of every building at a glance and drill into the sites that need attention most.",
  },
]

export function Features() {
  return (
    <section id="solutions" className="py-16 lg:py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <span className="text-sm font-semibold uppercase tracking-wider text-primary">
            One platform
          </span>
          <h2 className="mt-3 text-pretty text-3xl font-bold tracking-tight sm:text-4xl">
            Everything your facility teams need
          </h2>
          <p className="mt-4 text-pretty leading-relaxed text-muted-foreground">
            From the meter to the boardroom, ENGIE Digital FM connects operations, energy, and
            sustainability so you can run buildings that are efficient, resilient, and low-carbon.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="flex flex-col gap-3 rounded-xl border border-border bg-card p-6 transition-colors hover:border-primary/40"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-accent text-primary">
                <feature.icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <h3 className="text-lg font-semibold">{feature.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
