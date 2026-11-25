import { firmTeal, ink } from '../theme';

// Cover illustration for the landing page: a claim photo with a heatmap revealed over half of it,
// stamped as reviewed by a person. Drawn, so it uses no stock or dataset photo.
export default function CoverArt() {
  const split = 250;
  return (
    <svg viewBox="0 0 480 360" role="img" aria-label="A car damage photo, half shown as a heatmap, stamped as reviewed" style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <clipPath id="cover-photo"><rect x="24" y="24" width="432" height="268" rx="12" /></clipPath>
        <filter id="cover-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10" /></filter>
        <clipPath id="cover-heat"><rect x={split} y="24" width={456 - split} height="268" /></clipPath>
      </defs>

      {/* photo */}
      <rect x="16" y="16" width="448" height="284" rx="16" fill="#FFFFFF" stroke="#DCE0E3" />
      <g clipPath="url(#cover-photo)">
        <rect x="24" y="24" width="432" height="268" fill="#E4E9EC" />
        <rect x="24" y="226" width="432" height="66" fill="#CFD6DB" />
        <path d="M86 214 L104 178 L168 166 L212 128 L322 128 L364 166 L404 176 L414 214 Q414 226 402 226 L98 226 Q86 226 86 214 Z" fill="#8E9AA5" />
        <path d="M222 138 L316 138 L346 166 L190 166 Z" fill="#C7D2DA" />
        <line x1="268" y1="168" x2="268" y2="222" stroke="#7A8691" strokeWidth="2" />
        <path d="M282 184 q14 10 30 2 q-6 14 6 24" fill="none" stroke="#5E6872" strokeWidth="3" strokeLinecap="round" />
        <circle cx="152" cy="226" r="27" fill={ink} /><circle cx="152" cy="226" r="10" fill="#9AA5AE" />
        <circle cx="352" cy="226" r="27" fill={ink} /><circle cx="352" cy="226" r="10" fill="#9AA5AE" />

        {/* heatmap half */}
        <g clipPath="url(#cover-heat)">
          <rect x="24" y="24" width="432" height="268" fill="#22406F" opacity="0.78" />
          <g filter="url(#cover-blur)">
            <ellipse cx="300" cy="192" rx="58" ry="40" fill="#3FA7C9" opacity="0.7" />
            <ellipse cx="304" cy="194" rx="36" ry="24" fill="#F2C14E" opacity="0.9" />
            <ellipse cx="306" cy="195" rx="17" ry="12" fill="#E0503A" />
          </g>
        </g>
        <line x1={split} y1="24" x2={split} y2="292" stroke="#FFFFFF" strokeWidth="3" />
        <circle cx={split} cy="158" r="13" fill="#FFFFFF" stroke={ink} strokeOpacity="0.25" />
        <path d={`M${split - 5} 153 l-5 5 l5 5 M${split + 5} 153 l5 5 l-5 5`} fill="none" stroke={ink} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <rect x="36" y="36" width="64" height="22" rx="4" fill={ink} opacity="0.8" />
      <text x="68" y="51" textAnchor="middle" fontSize="11" fontWeight="600" fill="#FFFFFF" fontFamily="Public Sans, sans-serif">Original</text>
      <rect x="380" y="36" width="64" height="22" rx="4" fill={ink} opacity="0.8" />
      <text x="412" y="51" textAnchor="middle" fontSize="11" fontWeight="600" fill="#FFFFFF" fontFamily="Public Sans, sans-serif">Heatmap</text>

      {/* stamp */}
      <g transform="rotate(-7 388 300)">
        <rect x="312" y="270" width="150" height="62" rx="10" fill="#FFFFFF" fillOpacity="0.9" stroke={firmTeal} strokeWidth="3" />
        <rect x="317" y="275" width="140" height="52" rx="7" fill="none" stroke={firmTeal} strokeWidth="1" />
        <text x="387" y="302" textAnchor="middle" fontSize="22" fontWeight="700" fill={firmTeal} fontFamily="Source Serif 4, Georgia, serif">Reviewed</text>
        <text x="387" y="318" textAnchor="middle" fontSize="11" fontWeight="600" fill={firmTeal} fontFamily="Public Sans, sans-serif">by a person</text>
      </g>
    </svg>
  );
}
