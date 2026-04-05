'use client'

import { useCallback, useRef, useState } from 'react'
import SchoolProgramSelector from '@/components/SchoolProgramSelector'
import GradeInput             from '@/components/GradeInput'
import SupplementalCards      from '@/components/SupplementalCards'
import LoadingScreen          from '@/components/LoadingScreen'
import ResultView             from '@/components/ResultView'
import SummaryBar             from '@/components/SummaryBar'

import {
  AppView, EssayPair, FinalProbabilityResult, FormState, SchoolResult, SupplementalType,
} from '@/lib/types'
import { hasAdmittedProfile, PROGRAM_LABELS } from '@/lib/constants'

const INITIAL_FORM: FormState = {
  school: '', program: '', grade: '',
  supplementalTypes: [], supplementalTexts: {},
  supplementalCompleted: {}, activities: ['', ''],
  essayPairs: {},
}

function getApiSupplementalTypes(types: SupplementalType[]): string[] {
  return types.filter(t => t !== 'casper' && t !== 'none')
}

export default function Page() {
  const [view, setView]                   = useState<AppView>('form')
  const [form, setForm]                   = useState<FormState>(INITIAL_FORM)
  const [error, setError]                 = useState<string | null>(null)
  const [result, setResult]               = useState<FinalProbabilityResult | null>(null)
  const [submittedForm, setSubmittedForm] = useState<FormState | null>(null)
  const [schoolResults, setSchoolResults] = useState<SchoolResult[]>([])
  const timerDoneRef                      = useRef<boolean>(false)
  const apiResultRef                      = useRef<FinalProbabilityResult | null>(null)
  const timerResolveRef                   = useRef<(() => void) | null>(null)
  const apiResolveRef                     = useRef<((r: FinalProbabilityResult) => void) | null>(null)
  const apiRejectRef                      = useRef<((e: Error) => void) | null>(null)

  const gradeNum   = parseFloat(form.grade)
  const gradeValid = !isNaN(gradeNum) && gradeNum >= 50 && gradeNum <= 100
  const comboValid = !!(form.school && form.program && hasAdmittedProfile(form.school, form.program))
  const suppChosen = form.supplementalTypes.length > 0
  const canSubmit  = comboValid && gradeValid && suppChosen

  const setSchool = useCallback((school: string) => {
    setForm(f => ({ ...f, school, program: '' }))
    setError(null)
  }, [])

  const setProgram = useCallback((program: string) => {
    setForm(f => ({ ...f, program }))
    setError(null)
  }, [])

  const setGrade = useCallback((grade: string) => {
    setForm(f => ({ ...f, grade }))
  }, [])

  const toggleSupplemental = useCallback((type: SupplementalType) => {
    setForm(f => {
      // 'none' is exclusive
      if (type === 'none') {
        return { ...f, supplementalTypes: f.supplementalTypes.includes('none') ? [] : ['none'] }
      }
      // deselecting 'none' if another is picked
      const withoutNone = f.supplementalTypes.filter(t => t !== 'none')
      const already = withoutNone.includes(type)
      return {
        ...f,
        supplementalTypes: already
          ? withoutNone.filter(t => t !== type)
          : [...withoutNone, type],
      }
    })
  }, [])

  const setSupplementalText = useCallback((type: string, text: string) => {
    setForm(f => ({ ...f, supplementalTexts: { ...f.supplementalTexts, [type]: text } }))
  }, [])

  const setSupplementalCompleted = useCallback((type: string, done: boolean) => {
    setForm(f => ({ ...f, supplementalCompleted: { ...f.supplementalCompleted, [type]: done } }))
  }, [])

  const setActivity = useCallback((idx: number, text: string) => {
    setForm(f => {
      const next = [...f.activities]
      next[idx] = text
      return { ...f, activities: next }
    })
  }, [])

  const addActivity = useCallback(() => {
    setForm(f => ({ ...f, activities: [...f.activities, ''] }))
  }, [])

  const setEssayPair = useCallback((type: string, idx: number, field: keyof EssayPair, value: string) => {
    setForm(f => {
      const existing = f.essayPairs[type] ?? [{ question: '', answer: '' }]
      const next = existing.map((p, i) => i === idx ? { ...p, [field]: value } : p)
      return { ...f, essayPairs: { ...f.essayPairs, [type]: next } }
    })
  }, [])

  const addEssayPair = useCallback((type: string) => {
    setForm(f => {
      const existing = f.essayPairs[type] ?? [{ question: '', answer: '' }]
      return { ...f, essayPairs: { ...f.essayPairs, [type]: [...existing, { question: '', answer: '' }] } }
    })
  }, [])

  const removeEssayPair = useCallback((type: string, idx: number) => {
    setForm(f => {
      const existing = f.essayPairs[type] ?? []
      const next = existing.filter((_, i) => i !== idx)
      return { ...f, essayPairs: { ...f.essayPairs, [type]: next.length ? next : [{ question: '', answer: '' }] } }
    })
  }, [])

  async function handleSubmit() {
    if (!canSubmit) return
    setError(null)
    setView('loading')

    const snapshot = { ...form }
    setSubmittedForm(snapshot)

    const apiTypes = getApiSupplementalTypes(snapshot.supplementalTypes as SupplementalType[])

    // Build activity text if activity_list is selected
    const activityText = snapshot.supplementalTypes.includes('activity_list')
      ? snapshot.activities
          .filter(a => a.trim())
          .map((a, i) => `Activity ${i + 1}: ${a}`)
          .join('\n')
      : ''

    const supplementalTexts: Record<string, string> = { ...snapshot.supplementalTexts }
    if (activityText) supplementalTexts['activity_list'] = activityText

    // Serialize essay pairs into flat text for each written type
    for (const type of ['essay', 'aif'] as const) {
      if (snapshot.supplementalTypes.includes(type) && snapshot.supplementalCompleted[type]) {
        const pairs = snapshot.essayPairs[type] ?? []
        const filled = pairs.filter(p => p.question.trim() || p.answer.trim())
        if (filled.length > 0) {
          supplementalTexts[type] = filled
            .map((p, i) => `Question ${i + 1}: ${p.question}\nAnswer ${i + 1}: ${p.answer}`)
            .join('\n\n')
        }
      }
    }

    const timerPromise = new Promise<void>(resolve => {
      timerResolveRef.current = resolve
      setTimeout(resolve, 2500)
    })

    const apiPromise = fetch('/api/final-probability', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        school:                 snapshot.school,
        program:                snapshot.program,
        grade:                  parseFloat(snapshot.grade),
        supplementalTypes:      apiTypes,
        supplementalTexts,
        supplementalCompleted:  snapshot.supplementalCompleted,
      }),
    }).then(async res => {
      const data = await res.json() as FinalProbabilityResult & { error?: string }
      if (data.error) throw new Error(data.error)
      return data
    })

    try {
      const [, apiResult] = await Promise.all([timerPromise, apiPromise])
      setResult(apiResult)

      // Add to summary bar
      setSchoolResults(prev => {
        const key = `${snapshot.school}||${snapshot.program}`
        const filtered = prev.filter(r => `${r.school}||${r.program}` !== key)
        return [...filtered, {
          school:       snapshot.school,
          program:      snapshot.program,
          programLabel: PROGRAM_LABELS[snapshot.program] ?? snapshot.program,
          probability:  apiResult.probability,
          display_percent: apiResult.display_percent,
        }]
      })

      setView('result')
    } catch (err) {
      console.error(err)
      setError('Something went wrong calculating your probability. Please try again.')
      setView('form')
    }
  }

  function handleAnotherSchool() {
    setForm(f => ({
      ...INITIAL_FORM,
      grade:  f.grade,  // keep grade
    }))
    setResult(null)
    setError(null)
    setView('form')
  }

  function handleStartOver() {
    setForm(INITIAL_FORM)
    setResult(null)
    setSubmittedForm(null)
    setSchoolResults([])
    setError(null)
    setView('form')
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <SummaryBar results={schoolResults} />

      {view === 'loading' && <LoadingScreen />}

      {view === 'result' && result && submittedForm && (
        <ResultView
          school={submittedForm.school}
          program={submittedForm.program}
          grade={parseFloat(submittedForm.grade)}
          result={result}
          supplementalTypes={submittedForm.supplementalTypes as SupplementalType[]}
          onAnotherSchool={handleAnotherSchool}
          onStartOver={handleStartOver}
        />
      )}

      {view === 'form' && (
        <div className="flex-1 flex flex-col items-center px-4 pt-16 pb-16 max-w-lg mx-auto w-full">

          {/* Header */}
          <div className="w-full mb-10 animate-fade-up">
            <h1 className="font-display text-3xl text-[#f5f5f0] leading-tight">
              Know your odds.
            </h1>
            <p className="mt-2 text-sm text-[#f5f5f0]/45">
              Real outcomes from real Canadian applicants.
            </p>
          </div>

          {/* Form */}
          <div className="w-full space-y-8">
            <SchoolProgramSelector
              school={form.school}
              program={form.program}
              onSchool={setSchool}
              onProgram={setProgram}
            />

            {comboValid && (
              <GradeInput
                school={form.school}
                program={form.program}
                value={form.grade}
                onChange={setGrade}
              />
            )}

            {comboValid && gradeValid && (
              <SupplementalCards
                selected={form.supplementalTypes as SupplementalType[]}
                texts={form.supplementalTexts}
                completed={form.supplementalCompleted}
                activities={form.activities}
                essayPairs={form.essayPairs}
                onToggle={toggleSupplemental}
                onTextChange={setSupplementalText}
                onCompletedChange={setSupplementalCompleted}
                onActivityChange={setActivity}
                onAddActivity={addActivity}
                onEssayPairChange={setEssayPair}
                onAddEssayPair={addEssayPair}
                onRemoveEssayPair={removeEssayPair}
              />
            )}

            {error && (
              <p className="text-sm text-red-400/80 px-1 animate-fade-in">{error}</p>
            )}

            {comboValid && gradeValid && suppChosen && (
              <button
                type="button"
                onClick={handleSubmit}
                className="
                  w-full py-4 rounded-xl bg-[#3b82f6] text-white font-medium text-sm
                  hover:bg-[#2563eb] active:scale-[0.98] transition-all duration-150
                  animate-fade-up
                "
              >
                Calculate my odds
              </button>
            )}
          </div>

        </div>
      )}
    </div>
  )
}
