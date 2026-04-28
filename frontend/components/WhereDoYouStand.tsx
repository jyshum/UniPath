'use client'

import { useState } from 'react'

interface Props {
  avgAdmittedGrade: number | null
  gradeRange: { min: number; max: number } | null
  totalRecords: number
}

export default function WhereDoYouStand({ avgAdmittedGrade, gradeRange, totalRecords }: Props) {
  const [open, setOpen] = useState(false)
  const [grade, setGrade] = useState('')

  const gradeNum = parseFloat(grade)
  const valid = !isNaN(gradeNum) && gradeNum >= 50 && gradeNum <= 100

  let position: string | null = null
  if (valid && avgAdmittedGrade && gradeRange) {
    if (gradeNum >= gradeRange.max) {
      position = 'above the highest admitted grade on record'
    } else if (gradeNum >= avgAdmittedGrade) {
      position = 'above the average admitted grade'
    } else if (gradeNum >= gradeRange.min) {
      position = 'within the admitted range, but below average'
    } else {
      position = 'below the lowest admitted grade on record'
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-sm font-medium text-[#f5f5f0]">Where do you stand?</span>
        <span className="text-white/30 text-lg">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="px-6 pb-6 pt-2">
          <p className="text-xs text-white/40 mb-3">
            Enter your grade to see where you fall among admitted students.
          </p>
          <input
            type="number"
            min={50}
            max={100}
            step={0.1}
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            placeholder="Your average (e.g. 92.5)"
            className="w-full px-4 py-3 rounded-lg bg-white/[0.05] border border-white/10
                       text-[#f5f5f0] text-sm placeholder:text-white/20
                       focus:outline-none focus:border-white/30 transition-colors"
          />

          {valid && position && (
            <div className="mt-4 p-4 rounded-lg bg-white/[0.03] border border-white/10">
              <p className="text-sm text-[#f5f5f0]">
                With a <strong>{gradeNum}%</strong> average, you&apos;re {position}.
              </p>
              {avgAdmittedGrade && (
                <p className="text-xs text-white/30 mt-2">
                  Average admitted grade: {avgAdmittedGrade}%
                  {gradeRange && ` (range: ${gradeRange.min}–${gradeRange.max}%)`}
                </p>
              )}
            </div>
          )}

          {totalRecords < 20 && (
            <p className="text-xs text-yellow-500/50 mt-3">
              Based on limited data ({totalRecords} records). Results may not be representative.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
