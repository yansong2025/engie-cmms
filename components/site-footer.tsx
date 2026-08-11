import { buttonVariants } from "@/components/ui/button"
import { EngieLogo } from "@/components/engie-logo"
import { cn } from "@/lib/utils"

const columns = [
  { title: "Platform", links: ["Energy monitoring", "CMMS", "Analytics", "Reporting"] },
  { title: "Company", links: ["About ENGIE", "Careers", "Newsroom", "Contact"] },
  { title: "Resources", links: ["Documentation", "Case studies", "Support", "Status"] },
]

export function SiteFooter() {
  return (
    <footer id="insights" className="border-t border-border bg-secondary/40">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid gap-10 py-16 lg:grid-cols-[1.5fr_2fr]">
          <div className="flex flex-col gap-4">
            <div className="rounded-xl border border-border bg-card p-6">
              <h2 className="text-pretty text-2xl font-bold tracking-tight">
                Ready to digitize your buildings?
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                Talk to our team about bringing ENGIE Digital FM to your portfolio.
              </p>
              <a href="#analytics" className={cn(buttonVariants({ size: "lg" }), "mt-4")}>
                Request a demo
              </a>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            {columns.map((col) => (
              <div key={col.title} className="flex flex-col gap-3">
                <h3 className="text-sm font-semibold text-foreground">{col.title}</h3>
                <ul className="flex flex-col gap-2">
                  {col.links.map((link) => (
                    <li key={link}>
                      <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-start justify-between gap-4 border-t border-border py-6 sm:flex-row sm:items-center">
          <EngieLogo />
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} ENGIE Digital FM. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
