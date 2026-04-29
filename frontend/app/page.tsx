import ProgramCard from '@/components/ProgramCard'
import CategoryFilter from '@/components/CategoryFilter'
import { ProgramSummary } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

async function getPrograms(category?: string): Promise<ProgramSummary[]> {
  try {
    const url = category
      ? `${API_URL}/programs?category=${encodeURIComponent(category)}`
      : `${API_URL}/programs`
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>
}) {
  const { category } = await searchParams
  const programs = await getPrograms(category)

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-16 pb-16 max-w-4xl mx-auto w-full">
        <div className="mb-10">
          <h1 className="font-display text-3xl text-[#f5f5f0] leading-tight">
            See what it actually takes.
          </h1>
          <p className="mt-2 text-sm text-[#f5f5f0]/45">
            Grade distributions and EC patterns from real Canadian applicants.
          </p>
        </div>

        <CategoryFilter active={category ?? null} />

        {programs.length === 0 ? (
          <p className="text-white/40 mt-6">No program data available for this filter.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
            {programs.map((p) => (
              <ProgramCard
                key={`${p.school}|${p.program_name}`}
                school={p.school}
                programName={p.program_name}
                programCategory={p.program_category}
                dataTier={p.data_tier}
                totalRecords={p.total_records}
                accepted={p.accepted}
                overallAvg={p.overall_avg}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
