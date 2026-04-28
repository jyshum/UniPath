import Link from 'next/link'

interface Props {
  school: string
  program: string
  total: number
  accepted: number
}

const PROGRAM_LABELS: Record<string, string> = {
  ENGINEERING: 'Engineering',
  SCIENCE: 'Science',
  BUSINESS: 'Business',
  COMPUTER_SCIENCE: 'Computer Science',
  HEALTH: 'Health Sciences',
  ARTS: 'Arts',
}

export default function ProgramCard({ school, program, total, accepted }: Props) {
  const acceptRate = total > 0 ? Math.round((accepted / total) * 100) : 0
  const slug = `${encodeURIComponent(school)}/${encodeURIComponent(program)}`

  return (
    <Link
      href={`/program/${slug}`}
      className="block p-5 rounded-xl border border-white/10 bg-white/[0.03]
                 hover:bg-white/[0.06] hover:border-white/20 transition-all duration-200"
    >
      <p className="text-xs text-white/40 uppercase tracking-wide mb-1">{school}</p>
      <h3 className="text-lg font-medium text-[#f5f5f0] mb-3">
        {PROGRAM_LABELS[program] ?? program}
      </h3>
      <div className="flex items-center gap-4 text-sm text-white/50">
        <span>{total} records</span>
        <span>{acceptRate}% accepted</span>
      </div>
    </Link>
  )
}
