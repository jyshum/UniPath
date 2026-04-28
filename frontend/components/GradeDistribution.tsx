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
  const maxCount = Math.max(
    ...buckets.flatMap(b => [b.accepted, b.rejected, b.waitlisted, b.deferred]),
    1
  )

  return (
    <div>
      <h2 className="text-lg font-medium text-[#f5f5f0] mb-4">Grade Distribution</h2>
      <div className="space-y-3">
        {buckets.map((bucket) => {
          const total = bucket.accepted + bucket.rejected + bucket.waitlisted + bucket.deferred
          if (total === 0) return null
          return (
            <div key={bucket.bucket} className="flex items-center gap-3">
              <span className="text-sm text-white/50 w-16 text-right shrink-0">
                {bucket.bucket}
              </span>
              <div className="flex-1 flex gap-0.5 h-7">
                {(['accepted', 'rejected', 'waitlisted', 'deferred'] as const).map((decision) => {
                  const count = bucket[decision]
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
