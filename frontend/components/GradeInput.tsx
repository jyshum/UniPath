'use client'

import { useEffect, useRef, useState } from 'react'

interface Props {
  school:  string
  program: string
  value:   string
  onChange: (v: string) => void
}

export default function GradeInput({ school, program, value, onChange }: Props) {
  const [preview, setPreview]     = useState<string | null>(null)
  const [loading, setLoading]     = useState(false)
  const debounceRef               = useRef<ReturnType<typeof setTimeout> | null>(null)

  const gradeNum  = parseFloat(value)
  const isValid   = !isNaN(gradeNum) && gradeNum >= 50 && gradeNum <= 100

  useEffect(() => {
    if (!isValid) {
      setPreview(null)
      return
    }

    if (debounceRef.current) clearTimeout(debounceRef.current)

    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch('/api/base-probability', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ school, program, grade: gradeNum }),
        })
        const data = await res.json()
        if (data.error || !data.display_percent) {
          setPreview(null)
        } else {
          setPreview(data.display_percent)
        }
      } catch {
        setPreview(null)
      } finally {
        setLoading(false)
      }
    }, 500)
  }, [value, school, program, isValid, gradeNum])

  return (
    <div className="space-y-1.5 animate-fade-up">
      <label className="block text-xs font-medium tracking-widest uppercase text-[#f5f5f0]/40">
        Your top academic average (%)
      </label>

      <div className="relative">
        <input
          type="number"
          inputMode="decimal"
          min={50}
          max={100}
          step={0.1}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="e.g. 91.5"
          className={`
            w-full px-4 py-3.5 rounded-xl border bg-[#141414] text-[#f5f5f0]
            text-lg font-light placeholder-[#f5f5f0]/25 outline-none
            transition-all duration-150
            [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none
            ${value && !isValid
              ? 'border-red-500/50 focus:border-red-500/70'
              : 'border-white/10 focus:border-[#3b82f6]/60'
            }
          `}
        />
      </div>

      {/* Validation hint */}
      {value && !isValid && (
        <p className="text-xs text-red-400/80 px-1">Enter a number between 50 and 100.</p>
      )}

      {/* Live base preview */}
      {isValid && (
        <div className="flex items-center gap-2 px-1 h-5">
          {loading ? (
            <span className="text-xs text-[#f5f5f0]/30 animate-pulse">Calculating...</span>
          ) : preview ? (
            <span className="text-xs text-[#f5f5f0]/50">
              Grade alone:{' '}
              <span className="text-[#3b82f6]/80 font-medium">~{preview}</span>
            </span>
          ) : null}
        </div>
      )}
    </div>
  )
}
