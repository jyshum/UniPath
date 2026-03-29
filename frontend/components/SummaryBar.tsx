'use client'

import { SchoolResult } from '@/lib/types'

interface Props {
  results: SchoolResult[]
}

export default function SummaryBar({ results }: Props) {
  if (results.length === 0) return null

  const sorted = [...results].sort((a, b) => b.probability - a.probability)

  return (
    <div className="w-full border-b border-white/8 bg-[#0d0d0d] animate-fade-in">
      <div className="max-w-lg mx-auto px-4 py-3">
        <p className="text-xs text-[#f5f5f0]/35 tracking-wider uppercase mb-2">
          Your results so far
        </p>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {sorted.map((r, i) => (
            <div
              key={i}
              className="
                flex-shrink-0 flex items-center gap-2.5 px-3.5 py-2 rounded-lg
                border border-white/8 bg-[#141414]
              "
            >
              <div className="min-w-0">
                <p className="text-xs text-[#f5f5f0]/50 truncate max-w-[120px]">
                  {r.school.replace('University of ', 'U of ')} · {r.programLabel}
                </p>
              </div>
              <span className="text-sm font-semibold text-[#3b82f6] tabular-nums flex-shrink-0">
                {r.display_percent}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
