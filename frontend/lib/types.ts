// frontend/lib/types.ts

export interface ProgramSummary {
  school: string
  program_name: string
  program_category: string
  data_tier: 'official' | 'community' | 'both'
  total_records: number | null
  accepted: number | null
  overall_avg: number | null
}

export interface GradeBucket {
  bucket: string
  pct: number | null
  accepted: number | null
  rejected: number | null
  waitlisted: number | null
  deferred: number | null
}

export interface ECEntry {
  tag: string
  count: number
  pct: number
}

export interface ProgramStats {
  school: string
  program_name: string
  program_category: string
  data_tier: 'official' | 'community' | 'both'
  grade_distribution: GradeBucket[]
  ec_breakdown: ECEntry[]
  overall_avg: number | null
  historical: { year: number; overall_avg: number }[]
  total_records: number | null
  accepted_count: number | null
  avg_admitted_grade: number | null
  grade_range: { min: number; max: number } | null
  data_sources: Record<string, number>
}
