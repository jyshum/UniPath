// lib/constants.ts

export const SCHOOLS = [
  'UBC Vancouver',
  'University of Waterloo',
  'University of Toronto',
  'Western University',
  "Queen's University",
  'McMaster University',
  'Simon Fraser University',
]

export const PROGRAM_LABELS: Record<string, string> = {
  ENGINEERING:      'Engineering',
  SCIENCE:          'Science',
  BUSINESS:         'Business',
  COMPUTER_SCIENCE: 'Computer Science',
  HEALTH:           'Health Sciences',
  ARTS:             'Arts',
}

export const PROGRAMS_BY_SCHOOL: Record<string, string[]> = {
  'UBC Vancouver':           ['ENGINEERING', 'SCIENCE', 'BUSINESS', 'HEALTH', 'ARTS'],
  'University of Waterloo':  ['COMPUTER_SCIENCE', 'ENGINEERING'],
  'University of Toronto':   ['ENGINEERING', 'COMPUTER_SCIENCE', 'BUSINESS', 'SCIENCE'],
  'Western University':      ['BUSINESS'],
  "Queen's University":      ['BUSINESS'],
  'McMaster University':     ['HEALTH'],
  'Simon Fraser University': ['ENGINEERING', 'SCIENCE', 'BUSINESS'],
}

// Combos with full grade-adjusted data (ADMITTED_PROFILES in calibrate.py)
// Only these combos proceed past school/program selection in v1
export const ADMITTED_PROFILE_KEYS = new Set([
  'UBC Vancouver|ENGINEERING',
  'UBC Vancouver|SCIENCE',
  'UBC Vancouver|BUSINESS',
  'University of Waterloo|COMPUTER_SCIENCE',
  'University of Waterloo|ENGINEERING',
  'University of Toronto|ENGINEERING',
  'University of Toronto|COMPUTER_SCIENCE',
  'University of Toronto|BUSINESS',
  'Western University|BUSINESS',
  "Queen's University|BUSINESS",
  'McMaster University|HEALTH',
  'Simon Fraser University|ENGINEERING',
  'Simon Fraser University|SCIENCE',
])

export function hasAdmittedProfile(school: string, program: string): boolean {
  return ADMITTED_PROFILE_KEYS.has(`${school}|${program}`)
}

export function getPersonalityLine(pct: number): string {
  if (pct >= 75) return "Leave some for the rest of us 👀"
  if (pct >= 55) return "Who are you bro?! 🔥"
  if (pct >= 40) return "You're good bro 👍"
  if (pct >= 25) return "Don't worry, you've got this"
  if (pct >= 15) return "It's giving... risky 😬"
  return "You're so cooked 💀"
}

export const SUPPLEMENTAL_LABEL: Record<string, string> = {
  activity_list: 'Activity list',
  essay:         'Essay',
  aif:           'AIF',
  interview:     'Interview',
}
