export const AIBrainIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Left hemisphere */}
    <path d="M20 45 Q15 35 20 28 Q25 20 35 20 Q45 18 50 25 Q50 35 48 45 Q50 55 50 65 Q45 75 35 75 Q25 75 20 65 Q15 55 20 45 Z" 
          fill="none" stroke="currentColor" strokeWidth="2" />
    
    {/* Right hemisphere */}  
    <path d="M50 25 Q55 18 65 20 Q75 20 80 28 Q85 35 80 45 Q85 55 80 65 Q75 75 65 75 Q55 75 50 65 Q50 55 52 45 Q50 35 50 25 Z" 
          fill="none" stroke="currentColor" strokeWidth="2" />
    
    {/* Brain stem */}
    <path d="M45 75 Q50 80 55 75" stroke="currentColor" strokeWidth="2" />
    
    {/* Left hemisphere folds */}
    <path d="M25 35 Q30 38 28 42 Q32 45 30 50" stroke="currentColor" strokeWidth="1" />
    <path d="M22 50 Q26 53 24 58" stroke="currentColor" strokeWidth="1" />
    <path d="M30 60 Q35 62 33 67" stroke="currentColor" strokeWidth="1" />
    
    {/* Right hemisphere folds */}
    <path d="M75 35 Q70 38 72 42 Q68 45 70 50" stroke="currentColor" strokeWidth="1" />
    <path d="M78 50 Q74 53 76 58" stroke="currentColor" strokeWidth="1" />
    <path d="M70 60 Q65 62 67 67" stroke="currentColor" strokeWidth="1" />
    
    {/* Center connection */}
    <path d="M48 45 Q50 47 52 45" stroke="currentColor" strokeWidth="1" />
    <path d="M48 55 Q50 57 52 55" stroke="currentColor" strokeWidth="1" />
  </svg>
)