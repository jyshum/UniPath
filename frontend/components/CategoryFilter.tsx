'use client'

import { useRouter } from 'next/navigation'

const CATEGORIES = [
  { key: null, label: 'All' },
  { key: 'ENGINEERING', label: 'Engineering' },
  { key: 'SCIENCE', label: 'Science' },
  { key: 'BUSINESS', label: 'Business' },
  { key: 'COMPUTER_SCIENCE', label: 'Computer Science' },
  { key: 'HEALTH', label: 'Health' },
  { key: 'ARTS', label: 'Arts' },
]

interface Props {
  active: string | null
}

export default function CategoryFilter({ active }: Props) {
  const router = useRouter()

  return (
    <div className="flex flex-wrap gap-2">
      {CATEGORIES.map(({ key, label }) => {
        const isActive = active === key
        return (
          <button
            key={label}
            onClick={() => {
              const url = key ? `/?category=${key}` : '/'
              router.push(url)
            }}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              isActive
                ? 'bg-white/15 text-[#f5f5f0] border border-white/20'
                : 'bg-white/[0.03] text-white/40 border border-white/10 hover:text-white/60 hover:border-white/15'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
