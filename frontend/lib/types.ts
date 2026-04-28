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

export interface SimilarStudents {
  count:     number
  avg_grade: number
  min_grade: number
  max_grade: number
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
  similar_students?: SimilarStudents | null
}

export interface SchoolResult {
  school: string
  program: string
  programLabel: string
  probability: number
  display_percent: string
}

export type AppView = 'form' | 'loading' | 'result'

export interface ProgramSummary {
  school: string
  program: string
  total: number
  accepted: number
}

export interface GradeBucket {
  bucket: string
  accepted: number
  rejected: number
  waitlisted: number
  deferred: number
}

export interface ECEntry {
  tag: string
  count: number
  pct: number
}

export interface ProgramStats {
  school: string
  program: string
  grade_distribution: GradeBucket[]
  ec_breakdown: ECEntry[]
  total_records: number
  accepted_count: number
  avg_admitted_grade: number | null
  grade_range: { min: number; max: number } | null
  data_sources: Record<string, number>
}
