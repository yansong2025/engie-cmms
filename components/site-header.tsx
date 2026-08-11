import Link from "next/link"
import { buttonVariants } from "@/components/ui/button"
import { EngieLogo } from "@/components/engie-logo"
import { cn } from "@/lib/utils"

const navItems = [
  { label: "Platform", href: "#platform" },
  { label: "Analytics", href: "#analytics" },
  { label: "Solutions", href: "#solutions" },
  { label: "Insights", href: "#insights" },
]

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-6 px-4 sm:px-6">
        <Link href="#" aria-label="ENGIE digital FM home">
          <EngieLogo />
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {navItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href="#analytics"
            className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "hidden sm:inline-flex")}
          >
            Sign in
          </a>
          <a href="#analytics" className={cn(buttonVariants({ size: "lg" }))}>
            Request a demo
          </a>
        </div>
      </div>
    </header>
  )
}
