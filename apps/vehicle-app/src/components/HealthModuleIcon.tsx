import { Eye, Sparkles, Ear, HeartPulse } from 'lucide-react';
import type { HealthModule } from '../utils/healthModules';

export function HealthModuleIcon({ module, className = 'h-[18px] w-[18px]' }: { module: HealthModule; className?: string }) {
  if (module === 'dental') return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}><path d="M12 5c-2-2-6-2-7 1-1 3 1 6 2 9 .7 2 .8 5 2.3 5 1.4 0 1-5 2.7-5s1.3 5 2.7 5c1.5 0 1.6-3 2.3-5 1-3 3-6 2-9-1-3-5-3-7-1Z"/><path d="M9 4c1 1 2 2 4 2"/></svg>;
  const Icon = { vision: Eye, skin: Sparkles, hearing: Ear, mental: HeartPulse }[module];
  return <Icon aria-hidden="true" className={className} />;
}
