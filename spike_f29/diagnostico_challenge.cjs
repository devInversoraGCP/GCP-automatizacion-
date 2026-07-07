// diagnostico_challenge.cjs — Diagnostica qué pasa en CAutInicio.cgi
// No aborta temprano. Log del HTML, consola JS, y cambios de contenido.
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const CREDS_FILE = path.join(__dirname, 'data', '_creds.json');
const URL_LOGIN = 'https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html';
const DATA_DIR = path.join(__dirname, 'data');

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function randomSleep(min, max) { return sleep(min + Math.random() * (max - min)); }

(async () => {
  const creds = JSON.parse(fs.readFileSync(CREDS_FILE, 'utf-8'));

  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
    ],
    defaultViewport: { width: 1280, height: 800 },
  });

  const page = await browser.newPage();

  // Capturar mensajes de consola JS del challenge
  page.on('console', (msg) => {
    console.log(`  [JS console:${msg.type()}] ${msg.text().substring(0, 200)}`);
  });
  page.on('requestfailed', (req) => {
    console.log(`  [REQ FAIL] ${req.url().substring(0, 100)} — ${req.failure()?.errorText}`);
  });
  page.on('response', (resp) => {
    if (resp.url().includes('CAutInicio') || resp.url().includes('AUT2000')) {
      console.log(`  [HTTP ${resp.status()}] ${resp.url().substring(0, 120)}`);
    }
  });

  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['es-CL', 'es', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
  });

  console.log('🌐 Login...');
  await page.goto(URL_LOGIN, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await randomSleep(1500, 2500);
  await page.waitForSelector('#rutcntr', { timeout: 15000 });

  // Typing humanizado
  await page.click('#rutcntr');
  await page.evaluate(() => { document.querySelector('#rutcntr').value = ''; });
  for (const ch of creds.rut) { await page.keyboard.type(ch, { delay: 50 + Math.floor(Math.random() * 130) }); }
  await randomSleep(500, 1000);
  await page.click('#clave');
  await page.evaluate(() => { document.querySelector('#clave').value = ''; });
  for (const ch of creds.clave) { await page.keyboard.type(ch, { delay: 50 + Math.floor(Math.random() * 130) }); }
  await randomSleep(800, 1500);

  console.log('🖱️  Click Ingresar...');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {}),
    page.click('#bt_ingresar'),
  ]);

  console.log(`📍 URL post-click: ${page.url()}`);

  // Monitorear el challenge por 45 segundos, sin abortar
  console.log('\n━━━ Diagnóstico del challenge (45s) ━━━');
  let prevContentHash = '';
  for (let i = 0; i < 22; i++) {
    await sleep(2000);
    const elapsed = (i + 1) * 2;
    const url = page.url();
    const content = await page.content().catch(() => '');

    // Resumen del contenido (primeros 300 chars del body text)
    const bodyText = await page.evaluate(() => document.body?.innerText?.substring(0, 300) || '').catch(() => '');
    const contentHash = bodyText.substring(0, 100);

    if (contentHash !== prevContentHash) {
      console.log(`\n[${elapsed}s] URL: ${url.substring(0, 80)}`);
      console.log(`  contenido: "${bodyText.substring(0, 200).replace(/\n/g, ' ')}"`);
      prevContentHash = contentHash;
    } else {
      process.stdout.write('.');
    }

    // Guardar HTML completo del challenge para análisis
    if (i === 3 || i === 10) {
      const htmlFile = path.join(DATA_DIR, `challenge_html_${elapsed}s.html`);
      fs.writeFileSync(htmlFile, content, 'utf-8');
      console.log(`\n  📄 HTML guardado: data/challenge_html_${elapsed}s.html (${content.length} bytes)`);
    }

    // ¿URL cambió a Mi SII?
    if (!url.includes('CAutInicio.cgi') && !url.includes('IngresoRutClave')) {
      console.log(`\n✅ [${elapsed}s] URL cambió fuera del challenge: ${url}`);
      break;
    }
  }

  // Guardar HTML final
  const finalHtml = await page.content().catch(() => '');
  fs.writeFileSync(path.join(DATA_DIR, 'challenge_html_final.html'), finalHtml, 'utf-8');
  console.log(`\n📄 HTML final guardado: data/challenge_html_final.html (${finalHtml.length} bytes)`);

  await browser.close();
  try { fs.unlinkSync(CREDS_FILE); } catch (e) {}
  console.log('🧹 Done.');
})();
