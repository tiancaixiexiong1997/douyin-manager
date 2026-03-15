import React from 'react';

interface IconProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
});

export function LayoutDashboard({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  );
}

export function Users({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="8.5" cy="7" r="3.5" />
      <path d="M2 21v-1a6 6 0 0 1 6-6h1a6 6 0 0 1 6 6v1" />
      <path d="M16 3.5a3.5 3.5 0 0 1 0 7" />
      <path d="M22 21v-1a6 6 0 0 0-4-5.66" />
    </svg>
  );
}

export function Sparkles({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M12 2L13.8 8.2L20 10L13.8 11.8L12 18L10.2 11.8L4 10L10.2 8.2Z" />
      <path d="M19 2L19.9 4.6L22.5 5.5L19.9 6.4L19 9L18.1 6.4L15.5 5.5L18.1 4.6Z" />
      <path d="M5 17L5.7 19.1L7.8 19.8L5.7 20.5L5 22.6L4.3 20.5L2.2 19.8L4.3 19.1Z" />
    </svg>
  );
}

export function ChevronRight({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}

export function ChevronLeft({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

export function Zap({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style} fill="currentColor" stroke="none">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  );
}

export function Plus({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function X({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

export function Trash2({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M3 6h18" />
      <path d="M8 6V4h8v2" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v5M14 11v5" />
    </svg>
  );
}

export function RefreshCw({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </svg>
  );
}

export function ChevronDown({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export function ChevronUp({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M18 15l-6-6-6 6" />
    </svg>
  );
}

export function CheckCircle({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12l3 3 5-5" />
    </svg>
  );
}

export function Clock({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 3.5" />
    </svg>
  );
}

export function FileText({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8M16 17H8M10 9H8" />
    </svg>
  );
}

export function TrendingUp({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M23 6l-9.5 9.5-5-5L1 18" />
      <path d="M17 6h6v6" />
    </svg>
  );
}

export function ArrowRight({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M5 12h14" />
      <path d="M12 5l7 7-7 7" />
    </svg>
  );
}

export function ArrowLeft({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </svg>
  );
}

export function Loader2({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M21 12a9 9 0 1 1-6.22-8.56" />
    </svg>
  );
}

export function Calendar({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  );
}

export function Pencil({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

export function Save({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M17 21v-8H7v8M7 3v5h8" />
    </svg>
  );
}

export function Search({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

export function GitCompare({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="18" cy="18" r="3" />
      <circle cx="6" cy="6" r="3" />
      <path d="M6 21V9a9 9 0 0 0 9 9" />
      <path d="M18 3v12a9 9 0 0 1-9-9" />
    </svg>
  );
}

export function Filter({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  );
}

export function SettingsIcon({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

export function Link({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

export function Download({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

export function Sun({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M4.93 4.93l1.41 1.41" />
      <path d="M17.66 17.66l1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="M6.34 17.66l-1.41 1.41" />
      <path d="M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

export function Moon({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style}>
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  );
}

export function DouyinIcon({ size = 24, className, style }: IconProps) {
  return (
    <svg {...base(size)} className={className} style={style} fill="currentColor" stroke="none">
      <path d="M12.53.02C13.84 0 15.14.01 16.44 0c.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
    </svg>
  );
}

export function AppLogo({ size = 36, className, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" className={className} style={style}>
      <defs>
        {/* 小红书(Xiaohongshu)代表色：鲜亮偏玫红的红 (Top) */}
        <linearGradient id="c-xhs" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FF2442" />
          <stop offset="100%" stopColor="#FF6A7F" />
        </linearGradient>
        {/* 抖音(Douyin)代表色：青蓝 -> 紫红 (Left Bottom) */}
        <linearGradient id="c-douyin" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1CF2E8" />
          <stop offset="100%" stopColor="#FE2C55" />
        </linearGradient>
        {/* 视频号(VideoAccount)代表色：明黄色 -> 橘红色 (Right Bottom) */}
        <linearGradient id="c-video" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#F5A623" />
          <stop offset="100%" stopColor="#FA7114" />
        </linearGradient>
      </defs>

      {/* 统一的高级感暗色底板，带微弱发光边框 */}
      <rect width="36" height="36" rx="10" fill="#16161D" />
      <rect width="36" height="36" rx="10" fill="white" fillOpacity="0.04" />
      <rect width="36" height="36" rx="10" stroke="white" strokeOpacity="0.12" strokeWidth="1" />
      
      {/* 融合的三平台标志体：三个重叠的发光圆环 */}
      <g style={{ mixBlendMode: 'screen' }}>
        <circle cx="18" cy="13.5" r="7.8" fill="url(#c-xhs)" opacity="0.85" />
        <circle cx="13.5" cy="21" r="7.8" fill="url(#c-douyin)" opacity="0.85" />
        <circle cx="22.5" cy="21" r="7.8" fill="url(#c-video)" opacity="0.85" />
      </g>
      
      {/* 核心驱动力：白色的播放按钮/内容聚合点 */}
      <path d="M16.5 14.5 L22.5 18.5 L16.5 22.5 Z" fill="white" opacity="0.95" />
    </svg>
  );
}


