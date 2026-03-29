// app/api/final-probability/route.ts
// Called on form submit. Returns full final_probability() output.

export const runtime = 'nodejs'

import { callPython } from '@/lib/pythonBridge'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const {
      school,
      program,
      grade,
      supplementalTypes = [],
      supplementalTexts = {},
      supplementalCompleted = {},
      activities = [],
    } = body

    if (!school || !program || grade === undefined) {
      return Response.json({ error: 'missing_params' }, { status: 400 })
    }

    const result = await callPython('final_probability.py', {
      school,
      program,
      grade,
      supplemental_types:     supplementalTypes,
      supplemental_texts:     supplementalTexts,
      supplemental_completed: supplementalCompleted,
      activities,
    })

    return Response.json(result)
  } catch (err) {
    console.error('[final-probability]', err)
    return Response.json({ error: 'server_error' }, { status: 500 })
  }
}
