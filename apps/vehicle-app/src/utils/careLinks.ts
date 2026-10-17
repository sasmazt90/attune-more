/** Exact public source boundary; not proof of a booking or live availability. */
export function safeCareBookingUrl(value: unknown): string | undefined {
  if (typeof value !== 'string' || value.length > 2048 || /[\s\\]/.test(value)) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port || url.hash ||
        !['www.doktortakvimi.com','www.doktorsitesi.com','www.doctolib.de'].includes(url.hostname)) return undefined;
    const path = decodeURIComponent(value.match(/^https:\/\/[^/?#]+([^?#]*)/i)?.[1] || '/');
    if (!/^\/[a-zA-Z0-9_/-]*$/.test(path) || path.includes('//') || path.includes('..') ||
        path.split('/').some(p=>['redirect','redirects','out','login','auth','logout'].includes(p.toLowerCase()))) return undefined;
    if (url.search) {
      const keys=Array.from(url.searchParams.keys());
      if (url.hostname !== 'www.doktortakvimi.com' || path !== '/arama' || keys.length !== 2 ||
          !keys.includes('q') || !keys.includes('loc') ||
          keys.some(key=>!url.searchParams.get(key) || url.searchParams.get(key)!.includes('://'))) return undefined;
    }
    return value;
  } catch { return undefined; }
}
