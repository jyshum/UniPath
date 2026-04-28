// lib/types.ts

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
