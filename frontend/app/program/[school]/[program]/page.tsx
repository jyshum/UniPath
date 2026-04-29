import GradeDistribution from '@/components/GradeDistribution'
import ECBreakdown from '@/components/ECBreakdown'
import WhereDoYouStand from '@/components/WhereDoYouStand'
import SubmitOutcomeForm from '@/components/SubmitOutcomeForm'
import HistoricalTrends from '@/components/HistoricalTrends'
import Link from 'next/link'
import { ProgramStats } from '@/lib/types'

const API_URL = process.env.PYTHON_API_URL ?? 'http://localhost:8000'

async function getStats(school: string, programName: string): Promise<ProgramStats | null> {
  try {
    const res = await fetch(
      `${API_URL}/programs/${encodeURIComponent(school)}/${encodeURIComponent(programName)}`,
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
  const programName = decodeURIComponent(rawProgram)
  const stats = await getStats(school, programName)

  if (!stats) {
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
      if (src === 'CUDO_OFFICIAL') return `Official university data (CUDO)`
      if (src === 'REDDIT_SCRAPED') return `${count} Reddit posts`
      if (src === 'USER_SUBMITTED') return `${count} submissions`
      return `${count} ${src} records`
    })
    .join(' + ')

  const tierLabel = stats.data_tier === 'official'
    ? 'Official university data'
    : stats.data_tier === 'both'
    ? 'Official + community data'
    : 'Community-reported data'

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-12 pb-16 max-w-3xl mx-auto w-full">
        <Link href="/" className="text-sm text-white/30 hover:text-white/50 transition-colors">
          &larr; All programs
        </Link>

        <div className="mt-6 mb-10">
          <div className="flex items-center gap-3 mb-1">
            <p className="text-xs text-white/40 uppercase tracking-wide">{school}</p>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
              stats.data_tier === 'official' ? 'bg-emerald-500/20 text-emerald-400' :
              stats.data_tier === 'both' ? 'bg-purple-500/20 text-purple-400' :
              'bg-blue-500/20 text-blue-400'
            }`}>
              {tierLabel}
            </span>
          </div>
          <h1 className="font-display text-3xl text-[#f5f5f0]">{programName}</h1>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-10">
          {stats.overall_avg != null && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">{stats.overall_avg}%</p>
              <p className="text-xs text-white/40 mt-1">Avg admitted grade</p>
            </div>
          )}
          {stats.total_records != null && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-2xl font-medium text-[#f5f5f0]">{stats.total_records}</p>
              <p className="text-xs text-white/40 mt-1">Community records</p>
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

        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <GradeDistribution buckets={stats.grade_distribution} />
        </div>

        {stats.historical.length >= 2 && (
          <div className="mb-10">
            <HistoricalTrends data={stats.historical} />
          </div>
        )}

        {stats.ec_breakdown.length > 0 && stats.accepted_count != null && (
          <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
            <ECBreakdown entries={stats.ec_breakdown} acceptedCount={stats.accepted_count} />
          </div>
        )}

        {stats.data_tier === 'official' && (
          <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
            <p className="text-sm text-white/30">
              Community insights (extracurriculars, circumstances) are not yet available for this program.
              Submit your outcome below to contribute.
            </p>
          </div>
        )}

        <div className="mb-10">
          <WhereDoYouStand
            avgAdmittedGrade={stats.overall_avg ?? stats.avg_admitted_grade}
            gradeRange={stats.grade_range}
            totalRecords={stats.total_records ?? 0}
          />
        </div>

        <div className="mb-10 p-6 rounded-xl border border-white/10 bg-white/[0.03]">
          <SubmitOutcomeForm defaultSchool={school} defaultProgram={programName} />
        </div>

        <div className="text-xs text-white/20 text-center mt-8">
          {sourceLabel}
          {stats.total_records != null && stats.total_records < 20 && stats.data_tier !== 'official' && (
            <span className="block mt-1 text-yellow-500/50">
              Limited community data — take insights with a grain of salt
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
