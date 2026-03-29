'use client'

import { EssayPair, SupplementalType } from '@/lib/types'

const CARDS: { type: SupplementalType; label: string; icon: string }[] = [
  { type: 'none',          label: 'Nothing extra — grade only',              icon: '—' },
  { type: 'essay',         label: 'Written essay or personal statement',      icon: '✏️' },
  { type: 'aif',           label: 'Admission Information Form (AIF)',          icon: '📋' },
  { type: 'interview',     label: 'Interview',                                icon: '🎙' },
  { type: 'activity_list', label: 'Activity / extracurricular list',           icon: '📌' },
  { type: 'casper',        label: 'CASPer',                                   icon: '🧠' },
]

interface Props {
  selected:             SupplementalType[]
  texts:                Record<string, string>
  completed:            Record<string, boolean>
  activities:           string[]
  essayPairs:           Record<string, EssayPair[]>
  onToggle:             (t: SupplementalType) => void
  onTextChange:         (type: string, text: string) => void
  onCompletedChange:    (type: string, done: boolean) => void
  onActivityChange:     (idx: number, text: string) => void
  onAddActivity:        () => void
  onEssayPairChange:    (type: string, idx: number, field: keyof EssayPair, value: string) => void
  onAddEssayPair:       (type: string) => void
  onRemoveEssayPair:    (type: string, idx: number) => void
}

function WrittenExpansion({
  type,
  completed,
  pairs,
  onCompleted,
  onPairChange,
  onAddPair,
  onRemovePair,
}: {
  type:         string
  completed:    boolean
  pairs:        EssayPair[]
  onCompleted:  (done: boolean) => void
  onPairChange: (idx: number, field: keyof EssayPair, value: string) => void
  onAddPair:    () => void
  onRemovePair: (idx: number) => void
}) {
  return (
    <div className="mt-3 pt-3 border-t border-white/8 space-y-3 animate-fade-in">
      {/* Completed toggle */}
      <div className="flex gap-4">
        {[false, true].map(val => (
          <label key={String(val)} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name={`completed-${type}`}
              checked={completed === val}
              onChange={() => onCompleted(val)}
              className="w-3.5 h-3.5 accent-[#3b82f6]"
            />
            <span className="text-sm text-[#f5f5f0]/70">
              {val ? 'Yes' : 'Not yet'}
            </span>
          </label>
        ))}
      </div>

      {/* Multi Q&A pairs */}
      {completed && (
        <div className="animate-fade-up space-y-1">
          <details className="group">
            <summary className="cursor-pointer text-xs text-[#3b82f6]/70 hover:text-[#3b82f6] transition-colors list-none flex items-center gap-1">
              <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              Want a more accurate estimate? Paste your responses.{' '}
              <span className="text-[#f5f5f0]/30">(optional)</span>
            </summary>

            <div className="mt-3 space-y-4">
              {pairs.map((pair, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#f5f5f0]/35 uppercase tracking-wider">
                      Question {i + 1}
                    </span>
                    {pairs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => onRemovePair(i)}
                        className="text-xs text-[#f5f5f0]/25 hover:text-red-400/70 transition-colors"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <textarea
                    value={pair.question}
                    onChange={e => onPairChange(i, 'question', e.target.value)}
                    placeholder="Paste the prompt / question here"
                    rows={2}
                    className="
                      w-full px-3 py-2.5 rounded-lg border border-white/10 bg-[#0a0a0a]
                      text-sm text-[#f5f5f0] placeholder-[#f5f5f0]/25 resize-none outline-none
                      focus:border-[#3b82f6]/40 transition-colors
                    "
                  />
                  <textarea
                    value={pair.answer}
                    onChange={e => onPairChange(i, 'answer', e.target.value)}
                    placeholder="Paste your answer here"
                    rows={4}
                    className="
                      w-full px-3 py-2.5 rounded-lg border border-white/10 bg-[#0a0a0a]
                      text-sm text-[#f5f5f0] placeholder-[#f5f5f0]/25 resize-none outline-none
                      focus:border-[#3b82f6]/40 transition-colors
                    "
                  />
                </div>
              ))}

              {pairs.length < 10 && (
                <button
                  type="button"
                  onClick={onAddPair}
                  className="text-xs text-[#3b82f6]/60 hover:text-[#3b82f6] transition-colors flex items-center gap-1"
                >
                  <span>+</span> Add another question
                </button>
              )}
            </div>
          </details>
        </div>
      )}
    </div>
  )
}

function ActivityExpansion({
  activities,
  onActivityChange,
  onAddActivity,
}: {
  activities:       string[]
  onActivityChange: (idx: number, text: string) => void
  onAddActivity:    () => void
}) {
  return (
    <div className="mt-3 pt-3 border-t border-white/8 space-y-2 animate-fade-in">
      <p className="text-xs text-[#f5f5f0]/40">List your activities — each will be scored</p>
      {activities.map((act, i) => (
        <input
          key={i}
          type="text"
          value={act}
          onChange={e => onActivityChange(i, e.target.value)}
          placeholder={`Activity ${i + 1}`}
          className="
            w-full px-3 py-2 rounded-lg border border-white/8 bg-[#0a0a0a]
            text-sm text-[#f5f5f0] placeholder-[#f5f5f0]/25 outline-none
            focus:border-[#3b82f6]/40 transition-colors
          "
        />
      ))}
      {activities.length < 8 && (
        <button
          type="button"
          onClick={onAddActivity}
          className="text-xs text-[#3b82f6]/60 hover:text-[#3b82f6] transition-colors flex items-center gap-1"
        >
          <span>+</span> Add another activity
        </button>
      )}
    </div>
  )
}

export default function SupplementalCards({
  selected,
  texts,
  completed,
  activities,
  essayPairs,
  onToggle,
  onTextChange,
  onCompletedChange,
  onActivityChange,
  onAddActivity,
  onEssayPairChange,
  onAddEssayPair,
  onRemoveEssayPair,
}: Props) {
  return (
    <div className="space-y-3 animate-fade-up">
      <div>
        <h3 className="text-base font-medium text-[#f5f5f0]">
          What did your application include?
        </h3>
        <p className="text-sm text-[#f5f5f0]/45 mt-0.5">
          Select everything that applied to your application.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {CARDS.map(({ type, label, icon }) => {
          const isSelected = selected.includes(type)

          return (
            <div key={type}>
              <button
                type="button"
                onClick={() => onToggle(type)}
                className={`
                  w-full text-left px-4 py-3.5 rounded-xl border transition-all duration-150
                  ${isSelected
                    ? 'border-[#3b82f6]/50 bg-[#3b82f6]/8 text-[#f5f5f0]'
                    : 'border-white/8 bg-[#141414] hover:border-white/16 text-[#f5f5f0]/75 hover:text-[#f5f5f0]'
                  }
                `}
              >
                <div className="flex items-center gap-2.5">
                  <span className="text-base leading-none">{icon}</span>
                  <span className="text-sm font-light">{label}</span>
                </div>

                {/* Inline notes for interview / casper */}
                {isSelected && type === 'interview' && (
                  <p className="mt-2 text-xs text-[#f5f5f0]/40 leading-relaxed">
                    A standard adjustment is applied for interview requirements.
                    We can&apos;t evaluate interview performance.
                  </p>
                )}
                {isSelected && type === 'casper' && (
                  <p className="mt-2 text-xs text-[#f5f5f0]/40 leading-relaxed">
                    CASPer doesn&apos;t change your estimate — we can&apos;t evaluate it.
                  </p>
                )}
              </button>

              {/* Inline expansions */}
              {isSelected && (type === 'essay' || type === 'aif') && (
                <div className="px-4 pb-4 pt-1 bg-[#141414] border border-t-0 border-[#3b82f6]/50 rounded-b-xl -mt-1">
                  <WrittenExpansion
                    type={type}
                    completed={completed[type] ?? false}
                    pairs={essayPairs[type] ?? [{ question: '', answer: '' }]}
                    onCompleted={done => onCompletedChange(type, done)}
                    onPairChange={(idx, field, value) => onEssayPairChange(type, idx, field, value)}
                    onAddPair={() => onAddEssayPair(type)}
                    onRemovePair={idx => onRemoveEssayPair(type, idx)}
                  />
                </div>
              )}

              {isSelected && type === 'activity_list' && (
                <div className="px-4 pb-4 pt-1 bg-[#141414] border border-t-0 border-[#3b82f6]/50 rounded-b-xl -mt-1">
                  <ActivityExpansion
                    activities={activities}
                    onActivityChange={onActivityChange}
                    onAddActivity={onAddActivity}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
