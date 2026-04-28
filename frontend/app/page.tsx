import ProgramCard from '@/components/ProgramCard'
import { ProgramSummary } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

async function getPrograms(): Promise<ProgramSummary[]> {
  try {
    const res = await fetch(`${API_URL}/programs`, { cache: 'no-store' })
    if (!res.ok) return []
    return res.json()
  } catch {
    return []
  }
}

export default async function Home() {
  const programs = await getPrograms()

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

        {programs.length === 0 ? (
          <p className="text-white/40">No program data available yet.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {programs.map((p) => (
              <ProgramCard
                key={`${p.school}|${p.program}`}
                school={p.school}
                program={p.program}
                total={p.total}
                accepted={p.accepted}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
