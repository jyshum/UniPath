// lib/pythonBridge.ts
// In production (PYTHON_API_URL set): calls the FastAPI server on Railway via HTTP.
// In local dev (no PYTHON_API_URL): spawns a Python subprocess as before.

import { spawn } from 'child_process'
import path from 'path'

const SCRIPT_TO_ENDPOINT: Record<string, string> = {
  'final_probability.py': 'final-probability',
  'base_probability.py':  'base-probability',
}

export async function callPython(scriptName: string, input: object): Promise<object> {
  const apiUrl = process.env.PYTHON_API_URL

  if (apiUrl) {
    const endpoint = SCRIPT_TO_ENDPOINT[scriptName] ?? scriptName.replace('.py', '').replace(/_/g, '-')
    const res = await fetch(`${apiUrl}/${endpoint}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(input),
    })
    if (!res.ok) throw new Error(`Python API error: ${res.status}`)
    return res.json()
  }

  // Local dev: spawn subprocess
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'python_bridge', scriptName)
    const pythonBin  = process.env.PYTHON_PATH ?? 'python3'
    const proc       = spawn(pythonBin, [scriptPath])

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (data: Buffer) => { stdout += data.toString() })
    proc.stderr.on('data', (data: Buffer) => { stderr += data.toString() })

    proc.on('close', (code: number | null) => {
      if (code !== 0) {
        reject(new Error(`Python exited ${code}: ${stderr.slice(0, 500)}`))
        return
      }
      try {
        resolve(JSON.parse(stdout.trim()))
      } catch {
        reject(new Error(`Failed to parse Python output: ${stdout.slice(0, 200)}`))
      }
    })

    proc.on('error', (err: Error) => {
      reject(new Error(`Failed to spawn python3: ${err.message}`))
    })

    proc.stdin.write(JSON.stringify(input))
    proc.stdin.end()
  })
}
