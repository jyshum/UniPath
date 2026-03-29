// lib/types.ts

export type SupplementalType = 'none' | 'essay' | 'aif' | 'interview' | 'activity_list' | 'casper'

export interface EssayPair {
  question: string
  answer:   string
}

export interface FormState {
  school: string
  program: string
  grade: string
  supplementalTypes:     SupplementalType[]
  supplementalTexts:     Record<string, string>
  supplementalCompleted: Record<string, boolean>
  activities:            string[]
  essayPairs:            Record<string, EssayPair[]>
}

export interface BaseProbabilityResult {
  probability: number
  display_percent: string
  mode: string
  data_limited: boolean
}

export interface FinalProbabilityResult {
  probability: number
  display_percent: string
  base_probability: number
  supp_multipliers: number[]
  profile_multiplier: number
  confidence: string
  base_rate: number
  mean_admitted: number | null
  std_admitted: number | null
  data_limited: boolean
  disclaimer: string | null
  mode: string
}

export interface SchoolResult {
  school: string
  program: string
  programLabel: string
  probability: number
  display_percent: string
}

export type AppView = 'form' | 'loading' | 'result'
