// app/api/base-probability/route.ts
// Live grade preview — called on debounce as the user types their grade.

export const runtime = 'nodejs'

import { callPython } from '@/lib/pythonBridge'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { school, program, grade } = body

    if (!school || !program || grade === undefined) {
      return Response.json({ error: 'missing_params' }, { status: 400 })
    }

    const result = await callPython('base_probability.py', { school, program, grade })
    return Response.json(result)
  } catch (err) {
    console.error('[base-probability]', err)
    return Response.json({ error: 'server_error' }, { status: 500 })
  }
}
