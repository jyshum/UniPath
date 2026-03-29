'use client'

import { useState, useRef, useEffect } from 'react'
import { SCHOOLS, PROGRAMS_BY_SCHOOL, PROGRAM_LABELS, hasAdmittedProfile } from '@/lib/constants'

interface Props {
  school:    string
  program:   string
  onSchool:  (s: string) => void
  onProgram: (p: string) => void
}

function SearchableSelect({
  value,
  placeholder,
  options,
  onSelect,
  disabled = false,
}: {
  value:       string
  placeholder: string
  options:     { value: string; label: string }[]
  onSelect:    (v: string) => void
  disabled?:   boolean
}) {
  const [open,   setOpen]   = useState(false)
  const [query,  setQuery]  = useState('')
  const inputRef            = useRef<HTMLInputElement>(null)
  const containerRef        = useRef<HTMLDivElement>(null)

  const displayValue = value
    ? (options.find(o => o.value === value)?.label ?? value)
    : ''

  const filtered = options.filter(o =>
    o.label.toLowerCase().includes(query.toLowerCase())
  )

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function handleOpen() {
    if (disabled) return
    setOpen(true)
    setQuery('')
    setTimeout(() => inputRef.current?.focus(), 10)
  }

  function handleSelect(v: string) {
    onSelect(v)
    setOpen(false)
    setQuery('')
  }

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <button
        type="button"
        onClick={handleOpen}
        disabled={disabled}
        className={`
          w-full flex items-center justify-between px-4 py-3.5 rounded-xl border text-left
          transition-all duration-150
          ${disabled
            ? 'border-white/5 bg-white/3 text-[#f5f5f0]/25 cursor-not-allowed'
            : 'border-white/10 bg-[#141414] hover:border-white/20 cursor-pointer text-[#f5f5f0]'
          }
          ${open ? 'border-[#3b82f6]/60 bg-[#141414]' : ''}
        `}
      >
        <span className={value ? 'text-[#f5f5f0]' : 'text-[#f5f5f0]/35 font-light'}>
          {displayValue || placeholder}
        </span>
        <svg
          className={`w-4 h-4 text-[#f5f5f0]/40 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1.5 w-full bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
          <div className="p-2 border-b border-white/8">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Type to filter..."
              className="w-full bg-transparent text-sm text-[#f5f5f0] placeholder-[#f5f5f0]/30 outline-none px-2 py-1"
            />
          </div>
          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-4 py-2.5 text-sm text-[#f5f5f0]/35">No results</li>
            ) : (
              filtered.map(o => (
                <li key={o.value}>
                  <button
                    type="button"
                    onClick={() => handleSelect(o.value)}
                    className={`
                      w-full text-left px-4 py-2.5 text-sm transition-colors
                      ${o.value === value
                        ? 'text-[#3b82f6] bg-[#3b82f6]/10'
                        : 'text-[#f5f5f0] hover:bg-white/5'
                      }
                    `}
                  >
                    {o.label}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function SchoolProgramSelector({ school, program, onSchool, onProgram }: Props) {
  const schoolOptions  = SCHOOLS.map(s => ({ value: s, label: s }))
  const programOptions = school
    ? (PROGRAMS_BY_SCHOOL[school] ?? []).map(p => ({ value: p, label: PROGRAM_LABELS[p] ?? p }))
    : []

  const hasData = school && program ? hasAdmittedProfile(school, program) : null

  function handleSchoolChange(s: string) {
    onSchool(s)
    onProgram('')
  }

  return (
    <div className="space-y-4">
      {/* School */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium tracking-widest uppercase text-[#f5f5f0]/40">
          School
        </label>
        <SearchableSelect
          value={school}
          placeholder="Select a university"
          options={schoolOptions}
          onSelect={handleSchoolChange}
        />
      </div>

      {/* Program — slides in once school is chosen */}
      {school && (
        <div className="space-y-1.5 animate-fade-up">
          <label className="block text-xs font-medium tracking-widest uppercase text-[#f5f5f0]/40">
            Program
          </label>
          <SearchableSelect
            value={program}
            placeholder="Select a program"
            options={programOptions}
            onSelect={onProgram}
          />
        </div>
      )}

      {/* Status indicator */}
      {school && program && (
        <div className="animate-fade-up delay-100">
          {hasData ? (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-emerald-500/8 border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
              <span className="text-sm text-emerald-300/90">
                We have data for this program. Continue below.
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-amber-500/8 border border-amber-500/20">
              <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
              <span className="text-sm text-amber-300/90">
                We don&apos;t have enough data for this program yet. Try a different school or program.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
