import { AnalyticsUpload } from "@/components/analytics-upload"
import { EngieLogo } from "@/components/engie-logo"

export default function Page() {
  return (
    <main className="flex min-h-screen flex-col bg-background">
      <header className="flex justify-center pt-10 pb-2">
        <EngieLogo className="items-center text-center" />
      </header>
      <div className="flex flex-1 items-center justify-center">
        <AnalyticsUpload />
      </div>
    </main>
  )
}
