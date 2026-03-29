// lib/pythonBridge.ts
// Spawns a Python script, sends JSON via stdin, reads JSON from stdout.
// Scripts live in frontend/python_bridge/ and are run with process.cwd() = frontend/

import { spawn } from 'child_process'
import path from 'path'

export async function callPython(scriptName: string, input: object): Promise<object> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'python_bridge', scriptName)
    const pythonBin = process.env.PYTHON_PATH ?? 'python3'
    const proc = spawn(pythonBin, [scriptPath])

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
