import Link from 'next/link'

interface Props {
  school: string
  programName: string
  programCategory: string
  dataTier: 'official' | 'community' | 'both'
  totalRecords: number | null
  accepted: number | null
  overallAvg: number | null
}

const TIER_BADGE: Record<string, { label: string; color: string }> = {
  official: { label: 'Official', color: 'bg-emerald-500/20 text-emerald-400' },
  community: { label: 'Community', color: 'bg-blue-500/20 text-blue-400' },
  both: { label: 'Official + Community', color: 'bg-purple-500/20 text-purple-400' },
}

export default function ProgramCard({
  school,
  programName,
  programCategory,
  dataTier,
  totalRecords,
  accepted,
  overallAvg,
}: Props) {
  const slug = `${encodeURIComponent(school)}/${encodeURIComponent(programName)}`
  const badge = TIER_BADGE[dataTier]

  return (
    <Link
      href={`/program/${slug}`}
      className="block p-5 rounded-xl border border-white/10 bg-white/[0.03]
                 hover:bg-white/[0.06] hover:border-white/20 transition-all duration-200"
    >
      <div className="flex items-start justify-between mb-1">
        <p className="text-xs text-white/40 uppercase tracking-wide">{school}</p>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${badge.color}`}>
          {badge.label}
        </span>
      </div>
      <h3 className="text-lg font-medium text-[#f5f5f0] mb-3">{programName}</h3>
      <div className="flex items-center gap-4 text-sm text-white/50">
        {overallAvg != null && <span>Avg: {overallAvg}%</span>}
        {totalRecords != null && <span>{totalRecords} records</span>}
        {totalRecords != null && accepted != null && totalRecords > 0 && (
          <span>{Math.round((accepted / totalRecords) * 100)}% accepted</span>
        )}
      </div>
    </Link>
  )
}
