export const AIChipIcon = ({ className, isActive }: { className?: string; isActive?: boolean }) => (
  <div className={className}>
    <svg viewBox="0 0 100 100" fill="none" className="w-full h-full">
      {/* Central chip body */}
      <rect x="29.6" y="29.6" width="40.8" height="40.8" rx="5.4" stroke="currentColor" strokeWidth="2.4" fill="none" />
      <rect x="34.2" y="34.2" width="31.6" height="31.6" rx="2.7" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      {/* AI text */}
      <text x="50" y="55.2" textAnchor="middle" fill="currentColor" fontSize="15.2" fontFamily="Arial" fontWeight="bold">AI</text>
      
      {/* AI text overlay when active - stays lit */}
      {isActive && (
        <text x="50" y="55.2" textAnchor="middle" fill="#f6ff45" fontSize="15.2" fontFamily="Arial" fontWeight="bold">AI</text>
      )}
      
      {/* Top connections */}
      <line x1="38.2" y1="29.6" x2="38.2" y2="21" stroke="currentColor" strokeWidth="1.9" />
      <line x1="38.2" y1="21" x2="33.4" y2="16.2" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="31.5" cy="14.4" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="50" y1="29.6" x2="50" y2="9.6" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="50" cy="6.8" r="2.9" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="61.8" y1="29.6" x2="61.8" y2="21" stroke="currentColor" strokeWidth="1.9" />
      <line x1="61.8" y1="21" x2="66.6" y2="16.2" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="68.5" cy="14.4" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      {/* Left connections */}
      <line x1="29.6" y1="38.2" x2="21" y2="38.2" stroke="currentColor" strokeWidth="1.9" />
      <line x1="21" y1="38.2" x2="16.2" y2="33.4" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="14.4" cy="31.5" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="29.6" y1="50" x2="9.6" y2="50" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="6.8" cy="50" r="2.9" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="29.6" y1="61.8" x2="21" y2="61.8" stroke="currentColor" strokeWidth="1.9" />
      <line x1="21" y1="61.8" x2="16.2" y2="66.6" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="14.4" cy="68.5" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      {/* Right connections */}
      <line x1="70.4" y1="38.2" x2="79" y2="38.2" stroke="currentColor" strokeWidth="1.9" />
      <line x1="79" y1="38.2" x2="83.8" y2="33.4" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="85.6" cy="31.5" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="70.4" y1="50" x2="90.4" y2="50" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="93.2" cy="50" r="2.9" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="70.4" y1="61.8" x2="79" y2="61.8" stroke="currentColor" strokeWidth="1.9" />
      <line x1="79" y1="61.8" x2="83.8" y2="66.6" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="85.6" cy="68.5" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      {/* Bottom connections */}
      <line x1="38.2" y1="70.4" x2="38.2" y2="79" stroke="currentColor" strokeWidth="1.9" />
      <line x1="38.2" y1="79" x2="33.4" y2="83.8" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="31.5" cy="85.6" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="50" y1="70.4" x2="50" y2="90.4" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="50" cy="93.2" r="2.9" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      <line x1="61.8" y1="70.4" x2="61.8" y2="79" stroke="currentColor" strokeWidth="1.9" />
      <line x1="61.8" y1="79" x2="66.6" y2="83.8" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="68.5" cy="85.6" r="2.4" stroke="currentColor" strokeWidth="1.9" fill="none" />
      
      {/* Random pulsing lights when active */}
      {isActive && (
        <>
          <circle cx="50" cy="6.8" r="2.0" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '0.2s' }} />
          <circle cx="6.8" cy="50" r="2.0" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '1.4s' }} />
          <circle cx="93.2" cy="50" r="2.0" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '0.8s' }} />
          <circle cx="50" cy="93.2" r="2.0" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '2.1s' }} />
          <circle cx="31.5" cy="14.4" r="1.8" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '0.5s' }} />
          <circle cx="68.5" cy="14.4" r="1.8" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '1.7s' }} />
          <circle cx="31.5" cy="85.6" r="1.8" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '2.3s' }} />
          <circle cx="68.5" cy="85.6" r="1.8" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '1.1s' }} />
          <circle cx="85.6" cy="31.5" r="1.8" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '0.3s' }} />
          <circle cx="85.6" cy="68.5" r="1.8" fill="#f6ff45" stroke="#f6ff45" strokeWidth="3"
            style={{ animation: 'wave-travel 3s ease-in-out infinite', animationDelay: '2.7s' }} />
        </>
      )}
      
      {/* CSS animations */}
      <defs>
        <style>{`
          @keyframes wave-travel {
            0% { opacity: 0; }
            50% { opacity: 1; }
            100% { opacity: 0; }
          }
        `}</style>
      </defs>
    </svg>
  </div>
)