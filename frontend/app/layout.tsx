import type { Metadata } from 'next'
import { DM_Serif_Display, DM_Sans } from 'next/font/google'
import './globals.css'

const dmSerif = DM_Serif_Display({
  variable:  '--font-dm-serif',
  subsets:   ['latin'],
  weight:    '400',
  style:     ['normal', 'italic'],
  display:   'swap',
})

const dmSans = DM_Sans({
  variable: '--font-dm-sans',
  subsets:  ['latin'],
  weight:   ['300', '400', '500', '600'],
  display:  'swap',
})

export const metadata: Metadata = {
  title:       'UniPath — Know Your Odds',
  description: 'Calibrated university acceptance probabilities for Canadian students, based on real admission outcomes.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmSerif.variable} ${dmSans.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-[#0a0a0a] text-[#f5f5f0]">
        {children}
      </body>
    </html>
  )
}
