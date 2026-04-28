'use client'

import { ECEntry } from '@/lib/types'

interface Props {
  entries: ECEntry[]
  acceptedCount: number
}

const TAG_LABELS: Record<string, string> = {
  SPORTS: 'Sports',
  ARTS: 'Arts & Music',
  LEADERSHIP: 'Leadership',
  COMMUNITY_SERVICE: 'Community Service',
  WORK_EXPERIENCE: 'Work Experience',
  ACADEMIC_COMPETITION: 'Competitions',
  RESEARCH: 'Research',
  ENTREPRENEURSHIP: 'Entrepreneurship',
}

export default function ECBreakdown({ entries, acceptedCount }: Props) {
  if (entries.length === 0) return null

  const maxPct = Math.max(...entries.map(e => e.pct), 1)

  return (
    <div>
      <h2 className="text-lg font-medium text-[#f5f5f0] mb-1">
        What admitted students did
      </h2>
      <p className="text-xs text-white/30 mb-4">
        EC tags among {acceptedCount} accepted applicants
      </p>
      <div className="space-y-2.5">
        {entries.map((entry) => (
          <div key={entry.tag} className="flex items-center gap-3">
            <span className="text-sm text-white/60 w-32 text-right shrink-0">
              {TAG_LABELS[entry.tag] ?? entry.tag}
            </span>
            <div className="flex-1 h-6 bg-white/[0.03] rounded-sm overflow-hidden">
              <div
                className="h-full bg-[#3b82f6]/70 rounded-sm flex items-center px-2"
                style={{ width: `${(entry.pct / maxPct) * 100}%` }}
              >
                <span className="text-xs font-medium text-white/90">{entry.pct}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
