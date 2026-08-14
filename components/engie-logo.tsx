import { cn } from "@/lib/utils"

export function DigitalFMLogo({ className }: { className?: string }) {
  return (
    <div className={cn("inline-flex items-center leading-none", className)}>
      <span className="text-2xl font-light tracking-[0.06em] text-white sm:text-3xl">
        Digital <span className="font-semibold text-blue-500">FM</span>
      </span>
    </div>
  )
}