'use client'

export default function LoadingScreen() {
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-[#0a0a0a] z-40">

      {/* Breathing glow placeholder */}
      <div className="relative flex items-center justify-center">
        {/* Outer glow ring */}
        <div className="absolute w-48 h-48 rounded-full bg-[#3b82f6]/5 animate-breathe" />
        <div className="absolute w-32 h-32 rounded-full bg-[#3b82f6]/8 animate-breathe delay-200" />

        {/* Central pulsing block — where the number will appear */}
        <div className="relative z-10 flex flex-col items-center gap-2">
          <div
            className="w-36 h-20 rounded-2xl bg-gradient-to-br from-white/5 to-white/2 animate-pulse-glow"
            style={{ animationDuration: '3s' }}
          />
          <div className="w-20 h-2.5 rounded-full bg-white/5 animate-pulse" />
        </div>
      </div>

      {/* Corner label */}
      <div className="absolute bottom-8 right-8">
        <span className="text-xs text-[#f5f5f0]/20 tracking-widest uppercase">
          Calculating
          <span className="inline-flex gap-0.5 ml-1">
            {[0, 1, 2].map(i => (
              <span
                key={i}
                className="animate-bounce"
                style={{ animationDelay: `${i * 150}ms` }}
              >
                .
              </span>
            ))}
          </span>
        </span>
      </div>
    </div>
  )
}
