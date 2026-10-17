import Image from 'next/image';
import {Camera,Headphones,Sun,Scan,Volume2} from 'lucide-react';
export function HealthPreparation({module}:{module:'dental'|'hearing'}) {
 const dental=module==='dental';
 const items=dental?[[Camera,'Ön, sağ, sol ve rahat kapanış görünümü'],[Sun,'Dişleriniz iyi ışıkta net görünsün'],[Scan,'Ağzınıza cisim sokmadan rahatça gülümseyin']]:[[Headphones,'Stereo kulaklığınızı takın'],[Volume2,'Sessiz bir ortamda rahat ses ayarını koruyun'],[Scan,'Saf ses ve gürültüde sayı testlerini izleyin']];
 return <div data-health-preparation={module} className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
  <div className="lg:col-span-6 flex justify-center"><div className="w-full max-w-sm overflow-hidden rounded-3xl"><Image src={`/assets/${module}-preparation-v1.png`} width={1086} height={1448} alt={dental?'Doğal gülümsemede görünür dişler; ağız bölgesinde temsili hazırlık ağı':'Kulağa ulaşan temsili ses dalgalarıyla işitme testi hazırlığı'} className="w-full h-auto" priority/></div></div>
  <div className="lg:col-span-6 space-y-6 max-w-md"><h2 className="text-3xl font-extrabold text-white tracking-tight">{dental?'Diş Analizi':'İşitme Testi'}</h2><div className="space-y-3.5 pt-1">{items.map(([Icon,text],i)=>{const ItemIcon=Icon as typeof Camera;return <div key={i} className="flex items-center gap-3 text-sm text-slate-200"><div className="w-8 h-8 rounded-full bg-togg-turquoise/15 border border-togg-turquoise/30 flex items-center justify-center text-togg-turquoise shrink-0"><ItemIcon className="w-4 h-4"/></div><span>{text as string}</span></div>;})}</div></div>
 </div>;
}
