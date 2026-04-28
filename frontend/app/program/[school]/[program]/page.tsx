import GradeDistribution from '@/components/GradeDistribution'
import ECBreakdown from '@/components/ECBreakdown'
import Link from 'next/link'
import { ProgramStats } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

const PROGRAM_LABELS: Record<string, string> = {
  ENGINEERING: 'Engineering',
  SCIENCE: 'Science',
  BUSINESS: 'Business',
  COMPUTER_SCIENCE: 'Computer Science',
  HEALTH: 'Health Sciences',
  ARTS: 'Arts',
}

async function getStats(school: string, program: string): Promise<ProgramStats | null> {
  try {
    const res = await fetch(
      `${API_URL}/programs/${encodeURIComponent(school)}/${encodeURIComponent(program)}`,
      { cache: 'no-store' }
    )
    if (!res.ok) return null
    const data = await res.json()
    if (data.error) return null
    return data
  } catch {
    return null
  }
}

export default async function ProgramPage({
  params,
}: {
  params: Promise<{ school: string; program: string }>
}) {
  const { school: rawSchool, program: rawProgram } = await params
  const school = decodeURIComponent(rawSchool)
  const program = decodeURIComponent(rawProgram)
  const stats = await getStats(school, program)

  if (!stats || stats.total_records === 0) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-[#0a0a0a] px-4">
        <p className="text-white/40 mb-4">No data available for this program.</p>
        <Link href="/" className="text-[#3b82f6] hover:underline text-sm">
          Back to browse
        </Link>
      </div>
    )
  }

  const sourceLabel = Object.entries(stats.data_sources)
    .map(([src, count]) => {
      if (src === 'REDDIT_SCRAPED') return `${count} Reddit posts`
      if (src === 'USER_SUBMITTED') return `${count} submissions`
      return `${count} ${src} records`
    })
    .join(' + ')

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-12 pb-16 max-w-3xl mx-auto w-full">
        {/* Back link */}
        <Link href="/" className="text-sm text-white/30 hover:text-white/50 transition-colors">
          &larr; All programs
        </Link>

        {/* Header */}
        <div className="mt-6 mb-10">
          <p className="text-xs text-white/40 uppercase tracking-wide mb-1">{school}</p>
          <h1 className="font-display text-3xl text-[#f5f5f0]">
            {PROGRAM_LABELS[program] ?? program}
          </h1>
        </div>

        {/* Key stats */}
        <div className="grid grid-cols-3 gap-4 mb-10">
          <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
            <p className="text-2xl font-medium text-[#f5f5f0]">{stats.total_records}</p>
            <p className="text-xs text-white/40 mt-1">Records</p>
          </div>
          {stats.avg_admitted_grade && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">{stats.avg_admitted_grade}%</p>
              <p className="text-xs text-white/40 mt-1">Avg admitted grade</p>
            </div>
          )}
          {stats.grade_range && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">
                {stats.grade_range.min}–{stats.grade_range.max}%
              </p>
              <p className="text-xs text-white/40 mt-1">Admitted range</p>
            </div>
          )}
        </div>

        {/* Grade distribution */}
        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <GradeDistribution buckets={stats.grade_distribution} />
        </div>

        {/* EC breakdown */}
        {stats.ec_breakdown.length > 0 && (
          <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
            <ECBreakdown entries={stats.ec_breakdown} acceptedCount={stats.accepted_count} />
          </div>
        )}

        {/* Data provenance */}
        <div className="text-xs text-white/20 text-center mt-8">
          Based on {sourceLabel}
          {stats.total_records < 20 && (
            <span className="block mt-1 text-yellow-500/50">
              Limited data — take insights with a grain of salt
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
