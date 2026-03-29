'use client'

import { useEffect, useRef, useState } from 'react'
import { FinalProbabilityResult, SupplementalType } from '@/lib/types'
import { getPersonalityLine, PROGRAM_LABELS, SUPPLEMENTAL_LABEL } from '@/lib/constants'

interface Props {
  school:             string
  program:            string
  result:             FinalProbabilityResult
  supplementalTypes:  SupplementalType[]
  onAnotherSchool:    () => void
  onStartOver:        () => void
}

function useCountUp(target: number, duration = 800) {
  const [count, setCount] = useState(0)
  const rafRef            = useRef<number | null>(null)

  useEffect(() => {
    const start     = performance.now()
    const startVal  = 0

    function frame(now: number) {
      const elapsed  = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased    = 1 - Math.pow(1 - progress, 3) // easeOutCubic
      setCount(Math.round(startVal + (target - startVal) * eased))
      if (progress < 1) rafRef.current = requestAnimationFrame(frame)
    }

    rafRef.current = requestAnimationFrame(frame)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [target, duration])

  return count
}

export default function ResultView({
  school,
  program,
  result,
  supplementalTypes,
  onAnotherSchool,
  onStartOver,
}: Props) {
  const targetPct        = Math.round(result.probability * 100)
  const displayedPct     = useCountUp(targetPct)
  const programLabel     = PROGRAM_LABELS[program] ?? program
  const personalityLine  = getPersonalityLine(targetPct)

  // Build multiplier breakdown rows (skip 1.0 entries)
  const breakdownRows: { label: string; value: string }[] = []

  breakdownRows.push({
    label: 'Base probability (grade alone)',
    value: `${Math.round(result.base_probability * 100)}%`,
  })

  // Zip supplemental types with their multipliers (filter out casper / none)
  const scoredTypes = supplementalTypes.filter(t => t !== 'casper' && t !== 'none')
  scoredTypes.forEach((type, i) => {
    const m = result.supp_multipliers[i]
    if (m !== undefined && m !== 1.0) {
      const label = SUPPLEMENTAL_LABEL[type] ?? type
      breakdownRows.push({
        label: `${label} adjustment`,
        value: `×${m.toFixed(2)}`,
      })
    }
  })

  return (
    <div className="min-h-screen flex flex-col items-center px-4 pt-16 pb-16 max-w-lg mx-auto w-full">

      {/* School / program subtitle */}
      <p className="text-sm text-[#f5f5f0]/40 tracking-wide animate-fade-in">
        {school} · {programLabel}
      </p>

      {/* ── Hero percentage ── */}
      <div className="mt-6 mb-4 text-center animate-fade-up delay-100">
        <div
          className="font-display leading-none text-[#f5f5f0]"
          style={{ fontSize: 'clamp(80px, 22vw, 144px)' }}
        >
          {displayedPct}%
        </div>
      </div>

      {/* Personality line */}
      <p className="text-lg text-[#f5f5f0]/70 text-center animate-fade-up delay-200">
        {personalityLine}
      </p>

      {/* Confidence badge */}
      <div className="mt-4 animate-fade-up delay-300">
        <span className={`
          text-xs px-3 py-1 rounded-full border font-medium tracking-wide
          ${result.confidence === 'high'
            ? 'border-emerald-500/30 text-emerald-400/80 bg-emerald-500/8'
            : result.confidence === 'estimate'
              ? 'border-amber-500/30 text-amber-400/80 bg-amber-500/8'
              : 'border-white/15 text-[#f5f5f0]/40 bg-white/4'
          }
        `}>
          {result.confidence === 'high'    ? 'High confidence'
           : result.confidence === 'estimate' ? 'Estimate'
           : 'Low confidence'}
        </span>
      </div>

      {/* ── Breakdown collapsible ── */}
      <div className="w-full mt-10 animate-fade-up delay-400">
        <details className="group">
          <summary className="
            cursor-pointer list-none flex items-center justify-between
            px-5 py-4 rounded-xl border border-white/8 bg-[#141414]
            text-sm text-[#f5f5f0]/60 hover:text-[#f5f5f0] transition-colors
          ">
            <span>How was this calculated?</span>
            <svg
              className="w-4 h-4 transition-transform group-open:rotate-180 text-[#f5f5f0]/30"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </summary>

          <div className="mt-1 px-5 py-4 border border-white/8 rounded-xl bg-[#141414] space-y-2.5 animate-fade-in">
            {breakdownRows.map((row, i) => (
              <div key={i} className="flex justify-between items-baseline gap-4">
                <span className="text-sm text-[#f5f5f0]/55">{row.label}</span>
                <span className={`
                  text-sm font-medium tabular-nums flex-shrink-0
                  ${row.value.startsWith('×') && !row.value.includes('1.00')
                    ? (parseFloat(row.value.slice(1)) > 1 ? 'text-emerald-400' : 'text-red-400/80')
                    : 'text-[#f5f5f0]'
                  }
                `}>
                  {row.value}
                </span>
              </div>
            ))}
            <div className="pt-2 border-t border-white/8 flex justify-between items-baseline">
              <span className="text-sm text-[#f5f5f0]/80 font-medium">Final probability</span>
              <span className="text-sm font-semibold text-[#3b82f6]">{result.display_percent}</span>
            </div>
          </div>
        </details>
      </div>

      {/* ── Action buttons ── */}
      <div className="w-full mt-8 flex gap-3 animate-fade-up delay-500">
        <button
          type="button"
          onClick={onAnotherSchool}
          className="
            flex-1 px-4 py-3.5 rounded-xl border border-[#3b82f6]/40 bg-[#3b82f6]/8
            text-sm font-medium text-[#3b82f6] hover:bg-[#3b82f6]/14
            transition-all duration-150
          "
        >
          Another School
        </button>
        <button
          type="button"
          onClick={onStartOver}
          className="
            flex-1 px-4 py-3.5 rounded-xl border border-white/10 bg-[#141414]
            text-sm font-medium text-[#f5f5f0]/60 hover:text-[#f5f5f0] hover:border-white/20
            transition-all duration-150
          "
        >
          Start Over
        </button>
      </div>
    </div>
  )
}
