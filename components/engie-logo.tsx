import { cn } from "@/lib/utils"

export function EngieLogo({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col leading-none", className)}>
      <span className="text-xl font-bold tracking-[0.25em] text-primary">ENGIE</span>
      <span className="text-sm font-light tracking-[0.15em] text-foreground">
        digital <span className="font-normal text-primary">FM</span>
      </span>
    </div>
  )
}
