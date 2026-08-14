import { cn } from "@/lib/utils"

export function EngieLogo({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col leading-[0.95]", className)}>
      <span className="text-4xl font-bold tracking-[0.22em] text-primary sm:text-5xl">Digital</span>
      <span className="font-normal text-primary">FM</span>
    </div>
  )
}
