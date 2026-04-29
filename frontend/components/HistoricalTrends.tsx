'use client'

import { useState } from 'react'

interface Props {
  data: { year: number; overall_avg: number }[]
}

export default function HistoricalTrends({ data }: Props) {
  const [open, setOpen] = useState(false)

  if (data.length < 2) return null

  const minAvg = Math.min(...data.map(d => d.overall_avg))
  const maxAvg = Math.max(...data.map(d => d.overall_avg))
  const range = maxAvg - minAvg || 1

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-sm font-medium text-[#f5f5f0]">Historical Trends</span>
        <span className="text-white/30 text-lg">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="px-6 pb-6 pt-2">
          <p className="text-xs text-white/30 mb-4">
            Average admitted grade by year (CUDO official data)
          </p>
          <div className="space-y-2">
            {data.map((d) => {
              const pct = ((d.overall_avg - (minAvg - 2)) / (range + 4)) * 100
              return (
                <div key={d.year} className="flex items-center gap-3">
                  <span className="text-sm text-white/50 w-12 text-right shrink-0">
                    {d.year}
                  </span>
                  <div className="flex-1 h-6 bg-white/[0.03] rounded-sm overflow-hidden">
                    <div
                      className="h-full bg-emerald-500/50 rounded-sm flex items-center px-2"
                      style={{ width: `${Math.max(pct, 10)}%` }}
                    >
                      <span className="text-xs font-medium text-white/90">
                        {d.overall_avg}%
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
