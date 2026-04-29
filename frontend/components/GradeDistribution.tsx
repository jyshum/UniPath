'use client'

import { GradeBucket } from '@/lib/types'

interface Props {
  buckets: GradeBucket[]
}

const COLORS = {
  accepted: '#22c55e',
  rejected: '#ef4444',
  waitlisted: '#f59e0b',
  deferred: '#8b5cf6',
}

export default function GradeDistribution({ buckets }: Props) {
  const isPercentMode = buckets.length > 0 && buckets[0].pct != null

  if (isPercentMode) {
    const maxPct = Math.max(...buckets.map(b => b.pct ?? 0), 1)

    return (
      <div>
        <h2 className="text-lg font-medium text-[#f5f5f0] mb-4">Grade Distribution</h2>
        <div className="space-y-3">
          {buckets.map((bucket) => {
            const pct = bucket.pct ?? 0
            if (pct === 0) return null
            return (
              <div key={bucket.bucket} className="flex items-center gap-3">
                <span className="text-sm text-white/50 w-16 text-right shrink-0">
                  {bucket.bucket}
                </span>
                <div className="flex-1 h-7">
                  <div
                    className="h-full rounded-sm flex items-center justify-center text-xs font-medium"
                    style={{
                      width: `${(pct / maxPct) * 100}%`,
                      minWidth: '24px',
                      backgroundColor: '#3b82f6',
                    }}
                  >
                    {pct}%
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-white/20 mt-3">% of admitted students in each grade range</p>
      </div>
    )
  }

  // Count mode (existing behavior)
  const maxCount = Math.max(
    ...buckets.flatMap(b => [b.accepted ?? 0, b.rejected ?? 0, b.waitlisted ?? 0, b.deferred ?? 0]),
    1
  )

  return (
    <div>
      <h2 className="text-lg font-medium text-[#f5f5f0] mb-4">Grade Distribution</h2>
      <div className="space-y-3">
        {buckets.map((bucket) => {
          const total = (bucket.accepted ?? 0) + (bucket.rejected ?? 0) + (bucket.waitlisted ?? 0) + (bucket.deferred ?? 0)
          if (total === 0) return null
          return (
            <div key={bucket.bucket} className="flex items-center gap-3">
              <span className="text-sm text-white/50 w-16 text-right shrink-0">
                {bucket.bucket}
              </span>
              <div className="flex-1 flex gap-0.5 h-7">
                {(['accepted', 'rejected', 'waitlisted', 'deferred'] as const).map((decision) => {
                  const count = bucket[decision] ?? 0
                  if (count === 0) return null
                  const widthPct = (count / maxCount) * 100
                  return (
                    <div
                      key={decision}
                      className="h-full rounded-sm flex items-center justify-center text-xs font-medium"
                      style={{
                        width: `${widthPct}%`,
                        minWidth: count > 0 ? '20px' : '0',
                        backgroundColor: COLORS[decision],
                      }}
                    >
                      {count > 0 && count}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 mt-4 text-xs text-white/40">
        {Object.entries(COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
            <span className="capitalize">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
