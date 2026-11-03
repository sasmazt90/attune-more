#!/usr/bin/env node
/* Measures every page, dialog and expandable element across vehicle viewports.
 * Numbers come from the real rendered DOM. This is a layout audit only: it proves
 * nothing about analysis results, models or physical vehicles.
 *
 * ATTUNE_QA_PLAYWRIGHT  Path to a Playwright package (default: playwright)
 * ATTUNE_QA_CHROME      Chrome executable
 * ATTUNE_AUDIT_ORIGIN   Frontend origin (default: http://localhost:3000)
 * ATTUNE_AUDIT_OUT      Output directory
 * ATTUNE_AUDIT_LANGS    Comma list (default: en,de,tr)
 * ATTUNE_AUDIT_VIEWPORTS Comma list of viewport names (default: all)
 * ATTUNE_AUDIT_SHELLS   Comma list of aaos,web (default: both)
 * ATTUNE_AUDIT_SEED     Optional JSON of localStorage entries, for result and history states
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.ATTUNE_QA_PLAYWRIGHT || 'playwright');

const ROOT = path.resolve(__dirname, '../../..');
const ORIGIN = process.env.ATTUNE_AUDIT_ORIGIN || 'http://localhost:3000';
const OUT = path.resolve(process.env.ATTUNE_AUDIT_OUT || path.join(ROOT, 'output/automotive-audit'));
const LANGS = (process.env.ATTUNE_AUDIT_LANGS || 'en,de,tr').split(',');
const SHELL_CSS = fs.readFileSync(path.join(ROOT, 'apps/automotive/app/src/main/assets/automotive.css'), 'utf8');
const SEED = process.env.ATTUNE_AUDIT_SEED ? JSON.parse(fs.readFileSync(process.env.ATTUNE_AUDIT_SEED, 'utf8')) : null;

// "source" separates sizes taken from project evidence from ones added for wide or bar-heavy cars.
const VIEWPORTS = [
  { name: 'aaos-real-1280x517', width: 1280, height: 517, source: 'measured in the AAOS 15 WebView on the 1280x800 emulator, 2026-11-03' },
  { name: 'compact-800x480', width: 800, height: 480, source: 'project evidence 2026-10-28' },
  { name: 'wide-short-1024x400', width: 1024, height: 400, source: 'project evidence 2026-10-28' },
  { name: 'compact-1024x600', width: 1024, height: 600, source: 'project evidence 2026-10-28' },
  { name: 'bars-1280x620', width: 1280, height: 620, source: 'added: 1280x800 minus 180 px of system bars' },
  { name: 'hd-1280x720', width: 1280, height: 720, source: 'project evidence 2026-10-28' },
  { name: 'emulator-1280x800', width: 1280, height: 800, source: 'AAOS emulator physical display' },
  { name: 'ultrawide-1920x720', width: 1920, height: 720, source: 'added: wide OEM display class' },
  { name: 'full-hd-1920x1080', width: 1920, height: 1080, source: 'project evidence 2026-10-28' },
].filter(v => !process.env.ATTUNE_AUDIT_VIEWPORTS || process.env.ATTUNE_AUDIT_VIEWPORTS.split(',').includes(v.name));

const ROUTES = [
  { id: 'cockpit', path: '/' },
  { id: 'skin', path: '/skin', service: true },
  { id: 'vision', path: '/vision', service: true },
  { id: 'dental', path: '/dental', service: true },
  { id: 'hearing', path: '/hearing', service: true },
  { id: 'mental', path: '/mental', service: true },
  { id: 'care', path: '/care' },
  { id: 'history', path: '/profile' },
  { id: 'privacy', path: '/privacy' },
];

/** Runs in the page. Reports the facts a reviewer would otherwise estimate by eye. */
function measurePage() {
  const TEXT_MIN = 12;
  const visible = el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) !== 0;
  };
  const label = el => `${el.tagName.toLowerCase()}${el.getAttribute('data-testid') ? '#' + el.getAttribute('data-testid') : ''}:${(el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 40)}`;
  const header = document.querySelector('[data-cockpit-header]');
  const headerRect = header?.getBoundingClientRect();
  const sticky = header ? ['sticky', 'fixed'].includes(getComputedStyle(header).position) : false;
  const headerHeight = headerRect ? Math.round(headerRect.height) : 0;
  const usable = innerHeight - (sticky ? headerHeight : 0);
  const total = document.documentElement.scrollHeight;
  const scrollsSideways = el => {
    for (let node = el.parentElement; node; node = node.parentElement) {
      if (['auto', 'scroll', 'hidden'].includes(getComputedStyle(node).overflowX) && node !== document.body && node !== document.documentElement) return true;
    }
    return false;
  };
  const overflow = [];
  const smallText = { count: 0, samples: [] };
  for (const el of document.querySelectorAll('body *')) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > innerWidth + 1 || r.left < -1) && !scrollsSideways(el) && overflow.length < 12) overflow.push({ el: label(el), left: Math.round(r.left), right: Math.round(r.right) });
    const direct = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (direct && parseFloat(getComputedStyle(el).fontSize) < TEXT_MIN) {
      smallText.count++;
      if (smallText.samples.length < 6) smallText.samples.push({ el: label(el), px: parseFloat(getComputedStyle(el).fontSize) });
    }
  }
  const targets = [...document.querySelectorAll('button,a[href],summary,select,[role=button],input:not([type=hidden]):not([type=checkbox]):not([type=radio])')].filter(visible);
  const small = targets.filter(el => { const r = el.getBoundingClientRect(); return Math.min(r.width, r.height) < 44 - 0.5; });
  const hiddenBehind = targets.filter(el => {
    const r = el.getBoundingClientRect();
    if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) return false;
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return hit && !el.contains(hit) && !hit.contains(el);
  });
  const cta = [...document.querySelectorAll('main button')].find(el => visible(el) && !el.disabled && /^(Başlat|Start|Starten|Analizi Başlat|Yeni Analiz)/i.test((el.innerText || '').trim()));
  const ctaTop = cta ? cta.getBoundingClientRect().top + scrollY : null;
  return {
    inner: { width: innerWidth, height: innerHeight }, dpr: devicePixelRatio,
    header: { height: headerHeight, sticky, sharePct: Math.round(100 * headerHeight / innerHeight) },
    usableHeight: usable, totalHeight: total, viewportLengths: +(total / usable).toFixed(2),
    horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1 || overflow.length > 0, overflowSamples: overflow,
    primaryAction: cta ? { text: cta.innerText.trim().slice(0, 30), top: Math.round(ctaTop), viewportLengths: +(ctaTop / usable).toFixed(2), visibleWithoutScroll: ctaTop + cta.getBoundingClientRect().height <= innerHeight } : null,
    touch: { total: targets.length, belowMinimum: small.length, samples: small.slice(0, 6).map(el => ({ el: label(el), w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height) })) },
    smallText, covered: hiddenBehind.slice(0, 6).map(label),
  };
}

function measureDialog() {
  const panel = [...document.querySelectorAll('[role=dialog]')].pop();
  if (!panel) return null;
  const r = panel.getBoundingClientRect();
  const buttons = [...panel.querySelectorAll('button,a[href]')].filter(b => b.getClientRects().length);
  const inView = el => { const b = el.getBoundingClientRect(); return b.top >= r.top - 1 && b.bottom <= Math.min(r.bottom, innerHeight) + 1; };
  const closer = buttons.find(b => /kapat|close|schließ|schliess|tamam|^ok$|vazgeç|cancel|abbrechen|şimdi değil|not now|nicht jetzt/i.test(`${b.getAttribute('aria-label') || ''} ${b.innerText || ''}`));
  const enabled = buttons.filter(b => !b.disabled);
  const primary = enabled[enabled.length - 1] || null;
  const nestedScrollers = [...panel.querySelectorAll('*')].filter(el => { const s = getComputedStyle(el); return ['auto', 'scroll'].includes(s.overflowY) && el.scrollHeight > el.clientHeight + 1; }).length;
  return {
    title: panel.getAttribute('aria-label'),
    width: Math.round(r.width), height: Math.round(r.height),
    viewportSharePct: Math.round(100 * (r.width * r.height) / (innerWidth * innerHeight)),
    fitsViewport: r.top >= -1 && r.bottom <= innerHeight + 1 && r.left >= -1 && r.right <= innerWidth + 1,
    contentHeight: panel.scrollHeight, scrollsInternally: panel.scrollHeight > panel.clientHeight + 1,
    modalViewportLengths: +(panel.scrollHeight / Math.max(1, panel.clientHeight)).toFixed(2),
    closeVisible: closer ? inView(closer) : false, hasCloseControl: !!closer,
    primaryVisibleWithoutScroll: primary ? inView(primary) : null,
    nestedScrollers,
  };
}

async function settle(page) {
  await page.waitForLoadState('load').catch(() => {});
  await page.waitForTimeout(350);
}

async function setLanguage(page, lang) {
  await page.evaluate(l => localStorage.setItem('attune.language.v1', l), lang);
}

async function shot(page, directory, name) {
  await page.screenshot({ path: path.join(directory, name + '.png') }).catch(() => {});
}

async function passConsent(page, record, directory) {
  const dialog = page.locator('[role=dialog]').last();
  if (!(await dialog.count())) return false;
  const inside = await dialog.locator('input[type=checkbox]').count();
  if (!inside) return false;
  record.consent = await page.evaluate(measureDialog);
  await shot(page, directory, 'consent-open');
  await dialog.evaluate(el => el.scrollTo(0, el.scrollHeight));
  await shot(page, directory, 'consent-scrolled');
  for (let i = 0; i < inside; i++) {
    const box = dialog.locator('input[type=checkbox]').nth(i);
    if (!(await box.isChecked())) await box.check({ force: true }).catch(() => {});
  }
  const accept = dialog.locator('button:not([disabled])').first();
  await accept.click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(300);
  return true;
}

async function auditDialogs(page, record, directory) {
  record.dialogs = [];
  const triggers = page.locator('main [aria-haspopup="dialog"]:visible');
  const count = Math.min(await triggers.count(), 6);
  for (let i = 0; i < count; i++) {
    const trigger = page.locator('main [aria-haspopup="dialog"]:visible').nth(i);
    await trigger.scrollIntoViewIfNeeded().catch(() => {});
    const before = await page.evaluate(() => scrollY);
    await trigger.click({ timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(250);
    const metrics = await page.evaluate(measureDialog);
    if (!metrics) continue;
    await shot(page, directory, `dialog-${i}-open`);
    await page.locator('[role=dialog]').last().evaluate(el => el.scrollTo(0, el.scrollHeight));
    await page.waitForTimeout(80);
    metrics.closeVisibleAfterScroll = (await page.evaluate(measureDialog))?.closeVisible ?? false;
    await shot(page, directory, `dialog-${i}-scrolled`);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(150);
    metrics.closedWithEscape = !(await page.locator('[role=dialog]').count());
    metrics.scrollPreserved = Math.abs((await page.evaluate(() => scrollY)) - before) <= 2;
    record.dialogs.push(metrics);
    if (!metrics.closedWithEscape) break;
  }
}

async function auditExpandables(page, record, directory) {
  record.expandables = [];
  const all = page.locator('main details:visible, main [aria-expanded]:visible');
  const count = Math.min(await all.count(), 10);
  for (let i = 0; i < count; i++) {
    const item = page.locator('main details:visible, main [aria-expanded]:visible').nth(i);
    const data = await item.evaluate(el => {
      const control = el.tagName === 'DETAILS' ? el.querySelector('summary') : el;
      control.scrollIntoView({ block: 'center', behavior: 'instant' });
      const r = el.getBoundingClientRect();
      return { kind: el.tagName === 'DETAILS' ? 'details' : 'aria-expanded', text: (control.innerText || control.getAttribute('aria-label') || '').trim().slice(0, 50), collapsedHeight: Math.round(r.height), controlTop: Math.round(control.getBoundingClientRect().top), scrollY, pageHeight: document.documentElement.scrollHeight };
    }).catch(() => null);
    if (!data) continue;
    const control = (await item.evaluate(el => el.tagName)) === 'DETAILS' ? item.locator('summary').first() : item;
    await control.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(180);
    const open = await item.evaluate(el => {
      const c = el.tagName === 'DETAILS' ? el.querySelector('summary') : el;
      const r = el.getBoundingClientRect();
      return { expandedHeight: Math.round(r.height), controlTop: Math.round(c.getBoundingClientRect().top), scrollY, pageHeight: document.documentElement.scrollHeight, controlInView: c.getBoundingClientRect().top >= 0 && c.getBoundingClientRect().bottom <= innerHeight, overflowRight: r.right > innerWidth + 1 };
    }).catch(() => null);
    if (open) {
      await shot(page, directory, `expanded-${i}`);
      record.expandables.push({
        ...data, expandedHeight: open.expandedHeight, addedPageHeight: open.pageHeight - data.pageHeight,
        controlShiftPx: open.controlTop - data.controlTop, scrollChangedPx: open.scrollY - data.scrollY,
        closeControlInView: open.controlInView, overflowRight: open.overflowRight,
        extraViewportLengths: +((open.pageHeight - data.pageHeight) / (await page.evaluate(() => innerHeight))).toFixed(2),
      });
    }
    await control.click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(100);
  }
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.ATTUNE_QA_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const results = [];
  for (const shell of (process.env.ATTUNE_AUDIT_SHELLS || 'aaos,web').split(',')) {
    for (const viewport of VIEWPORTS) {
      for (const lang of LANGS) {
        const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
        const page = await context.newPage();
        page.setDefaultTimeout(8000);
        await page.goto(ORIGIN + '/', { waitUntil: 'load' });
        await setLanguage(page, lang);
        if (SEED) await page.evaluate(entries => { for (const [k, v] of Object.entries(entries)) localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v)); }, SEED);
        for (const route of ROUTES) {
          const directory = path.join(OUT, shell, viewport.name, lang, route.id);
          fs.mkdirSync(directory, { recursive: true });
          const record = { shell, viewport: viewport.name, viewportSource: viewport.source, lang, route: route.id };
          try {
            await page.goto(ORIGIN + route.path, { waitUntil: 'load' });
            if (shell === 'aaos') await page.addStyleTag({ content: SHELL_CSS }).then(h => h.evaluate(el => { el.id = 'attune-automotive-style'; }));
            await settle(page);
            if (route.service) await passConsent(page, record, directory);
            await settle(page);
            record.page = await page.evaluate(measurePage);
            await shot(page, directory, 'top');
            await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
            await page.waitForTimeout(120);
            await shot(page, directory, 'bottom');
            await page.evaluate(() => scrollTo(0, 0));
            if (shell === 'aaos' || viewport.name === 'hd-1280x720') {
              await auditDialogs(page, record, directory);
              await page.evaluate(() => scrollTo(0, 0));
              await auditExpandables(page, record, directory);
            }
          } catch (error) {
            record.error = String(error).slice(0, 300);
          }
          results.push(record);
          fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify(results, null, 1));
        }
        await context.close();
      }
    }
  }
  await browser.close();
  console.log(JSON.stringify({ out: OUT, records: results.length, errors: results.filter(r => r.error).length }));
}

main().catch(error => { console.error(error); process.exit(1); });
