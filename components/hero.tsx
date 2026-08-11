import Image from "next/image"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const stats = [
  { value: "18%", label: "Average energy savings" },
  { value: "2,400+", label: "Buildings monitored" },
  { value: "24/7", label: "Real-time oversight" },
]

export function Hero() {
  return (
    <section id="platform" className="relative overflow-hidden border-b border-border">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
        <div className="flex flex-col gap-6">
          <span className="inline-flex w-fit items-center gap-2 rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            Intelligent Facility Management
          </span>

          <h1 className="text-pretty text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            Turn building data into <span className="text-primary">smarter operations</span>
          </h1>

          <p className="max-w-lg text-pretty text-lg leading-relaxed text-muted-foreground">
            ENGIE Digital FM unifies your CMMS, utility, and asset data into one platform — so your
            teams can cut energy waste, plan maintenance with confidence, and hit sustainability targets.
          </p>

          <div className="flex flex-col gap-3 sm:flex-row">
            <a href="#analytics" className={cn(buttonVariants({ size: "lg" }))}>
              Analyze your utility data
            </a>
            <a href="#solutions" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
              Explore solutions
            </a>
          </div>

          <dl className="mt-4 grid grid-cols-3 gap-6 border-t border-border pt-6">
            {stats.map((stat) => (
              <div key={stat.label}>
                <dt className="sr-only">{stat.label}</dt>
                <dd className="text-2xl font-bold text-foreground">{stat.value}</dd>
                <dd className="mt-1 text-xs leading-snug text-muted-foreground">{stat.label}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="relative">
          <div className="relative aspect-[4/3] overflow-hidden rounded-xl border border-border shadow-sm">
            <Image
              src="/smart-building.png"
              alt="Modern glass office tower managed by ENGIE Digital FM"
              fill
              priority
              className="object-cover"
              sizes="(max-width: 1024px) 100vw, 50vw"
            />
          </div>
        </div>
      </div>
    </section>
  )
}
