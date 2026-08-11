import { SiteHeader } from "@/components/site-header"
import { Hero } from "@/components/hero"
import { AnalyticsUpload } from "@/components/analytics-upload"
import { Features } from "@/components/features"
import { SiteFooter } from "@/components/site-footer"

export default function Page() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <AnalyticsUpload />
        <Features />
      </main>
      <SiteFooter />
    </div>
  )
}
