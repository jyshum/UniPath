'use client'

import { useState } from 'react'

interface Props {
  defaultSchool?: string
  defaultProgram?: string
}

const API_URL = process.env.NEXT_PUBLIC_PYTHON_API_URL ?? 'http://localhost:8000'

export default function SubmitOutcomeForm({ defaultSchool, defaultProgram }: Props) {
  const [school, setSchool] = useState(defaultSchool ?? '')
  const [program, setProgram] = useState(defaultProgram ?? '')
  const [grade, setGrade] = useState('')
  const [decision, setDecision] = useState('')
  const [ecs, setEcs] = useState('')
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle')

  const gradeNum = parseFloat(grade)
  const canSubmit = school && program && !isNaN(gradeNum) && gradeNum >= 50 && gradeNum <= 100 && decision

  async function handleSubmit() {
    if (!canSubmit) return
    setStatus('submitting')
    try {
      const res = await fetch(`${API_URL}/submit-outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          school,
          program,
          grade: gradeNum,
          decision,
          ecs: ecs || undefined,
        }),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setStatus('success')
    } catch {
      setStatus('error')
    }
  }

  if (status === 'success') {
    return (
      <div className="p-6 rounded-xl border border-green-500/20 bg-green-500/[0.05] text-center">
        <p className="text-sm text-green-400">Thanks for contributing! Your data helps future applicants.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-[#f5f5f0]">Got your result? Add your outcome.</h3>
      <p className="text-xs text-white/30">Anonymous. Helps future applicants.</p>

      <div className="grid grid-cols-2 gap-3">
        <input
          type="text"
          value={school}
          onChange={(e) => setSchool(e.target.value)}
          placeholder="School (e.g. UBC)"
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0] placeholder:text-white/20
                     focus:outline-none focus:border-white/30"
        />
        <input
          type="text"
          value={program}
          onChange={(e) => setProgram(e.target.value)}
          placeholder="Program (e.g. Engineering)"
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0] placeholder:text-white/20
                     focus:outline-none focus:border-white/30"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <input
          type="number"
          min={50}
          max={100}
          step={0.1}
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          placeholder="Your average (50-100)"
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0] placeholder:text-white/20
                     focus:outline-none focus:border-white/30"
        />
        <select
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          className="px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                     text-sm text-[#f5f5f0]
                     focus:outline-none focus:border-white/30"
        >
          <option value="">Decision...</option>
          <option value="Accepted">Accepted</option>
          <option value="Rejected">Rejected</option>
          <option value="Waitlisted">Waitlisted</option>
          <option value="Deferred">Deferred</option>
        </select>
      </div>

      <textarea
        value={ecs}
        onChange={(e) => setEcs(e.target.value)}
        placeholder="Extracurriculars (optional — e.g. robotics club, volunteering, varsity basketball)"
        rows={2}
        className="w-full px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10
                   text-sm text-[#f5f5f0] placeholder:text-white/20
                   focus:outline-none focus:border-white/30 resize-none"
      />

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || status === 'submitting'}
        className="w-full py-3 rounded-lg bg-[#3b82f6] text-white text-sm font-medium
                   hover:bg-[#2563eb] disabled:opacity-30 disabled:cursor-not-allowed
                   transition-all duration-150"
      >
        {status === 'submitting' ? 'Submitting...' : 'Submit outcome'}
      </button>

      {status === 'error' && (
        <p className="text-xs text-red-400/70">Something went wrong. Try again.</p>
      )}
    </div>
  )
}
