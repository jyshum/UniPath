import SubmitOutcomeForm from '@/components/SubmitOutcomeForm'
import Link from 'next/link'

export default function SubmitPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <div className="flex-1 px-4 pt-16 pb-16 max-w-lg mx-auto w-full">
        <Link href="/" className="text-sm text-white/30 hover:text-white/50 transition-colors">
          &larr; Browse programs
        </Link>
        <div className="mt-6 mb-8">
          <h1 className="font-display text-2xl text-[#f5f5f0]">Share your outcome</h1>
          <p className="mt-2 text-sm text-white/40">
            Help future applicants by contributing your admission result. Anonymous, no account needed.
          </p>
        </div>
        <SubmitOutcomeForm />
      </div>
    </div>
  )
}
