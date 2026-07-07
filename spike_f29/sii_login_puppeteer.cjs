// sii_login_puppeteer.cjs — Login SII con puppeteer-extra + StealthPlugin
// v2: detección corregida + headless:'new' + espera real de challenge F5 BIG-IP
//
// Hallazgos de la investigación del usuario:
//  1. F5 BIG-IP anti-bot: CAutInicio.cgi sirve un JS challenge que fingerprintea
//  2. puppeteer-extra + StealthPlugin bypassa la detección
//  3. headless: 'new' + --disable-blink-features=AutomationControlled
//  4. NO abortar en CAutInicio.cgi — esperar a que el challenge redirija
//
// v2 corrige: detección de "Mi Sii" en nav bar = falso positivo.
//   La verificación real es: URL cambia a algo que NO sea CAutInicio.cgi ni login.
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const CREDS_FILE = path.join(__dirname, 'data', '_creds.json');
const URL_LOGIN = 'https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html';
const CAPT_DIR = path.join(__dirname, 'capturas');

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function randomSleep(min, max) { return sleep(min + Math.random() * (max - min)); }

async function typeHuman(page, selector, text) {
  await page.click(selector);
  await randomSleep(300, 800);
  await page.evaluate((sel) => { const el = document.querySelector(sel); if (el) el.value = ''; }, selector);
  for (const ch of text) {
    await page.keyboard.type(ch, { delay: 50 + Math.floor(Math.random() * 130) });
  }
}

function esUrlDeError(url) {
  // CAutInicio.cgi = challenge page; IngresoRutClave = login page
  return url.includes('CAutInicio.cgi') || url.includes('IngresoRutClave');
}

(async () => {
  console.log('🔐 Leyendo credenciales (R1: en memoria, no se imprimen)...');
  const creds = JSON.parse(fs.readFileSync(CREDS_FILE, 'utf-8'));

  console.log('🚀 Lanzando Chrome con puppeteer-extra + StealthPlugin...');
  console.log('   headless: new, --disable-blink-features=AutomationControlled');
  const browser = await puppeteer.launch({
    headless: 'new',  // modo headless menos detectable (investigación del usuario)
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-features=IsolateOrigins,site-per-process',
      '--window-size=1280,800',
    ],
    defaultViewport: { width: 1280, height: 800 },
  });

  const page = await browser.newPage();

  // Stealth extra a nivel de página
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['es-CL', 'es', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
  });

  console.log('🌐 Navegando al login del SII...');
  await page.goto(URL_LOGIN, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await randomSleep(1500, 3000);

  await page.waitForSelector('#rutcntr', { timeout: 15000 });

  console.log('⌨️  Typing RUT (humanizado)...');
  await typeHuman(page, '#rutcntr', creds.rut);
  await randomSleep(500, 1500);

  console.log('⌨️  Typing clave (humanizado)...');
  await typeHuman(page, '#clave', creds.clave);
  await randomSleep(800, 2000);

  console.log('🖱️  Click "Ingresar"...');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {}),
    page.click('#bt_ingresar'),
  ]);

  // ─── CLAVE: esperar al challenge F5 BIG-IP en CAutInicio.cgi ───
  // El challenge es un JS que fingerprintea el browser y redirige si pasa.
  // NO abortar si vemos "no se puede responder" inmediatamente —
  // puede aparecer brevemente antes de que el JS complete.
  console.log('⏳ Challenge F5 BIG-IP en CAutInicio.cgi...');
  let currentUrl = page.url();
  console.log(`   URL post-click: ${currentUrl}`);

  const startTime = Date.now();
  let success = false;
  let errorDetected = false;

  while (Date.now() - startTime < 60000) {
    await sleep(2000);
    const newUrl = page.url();
    const elapsed = Math.floor((Date.now() - startTime) / 1000);

    if (newUrl !== currentUrl) {
      console.log(`   [${elapsed}s] URL cambió: ${newUrl}`);
      currentUrl = newUrl;
    }

    // ¿Salimos de CAutInicio.cgi a una URL real de Mi SII?
    if (!esUrlDeError(currentUrl)) {
      // Verificar que NO sea la página de error con "no se puede responder"
      const content = await page.content().catch(() => '');
      if (!content.toLowerCase().includes('no se puede responder a sus requerimientos')) {
        console.log(`✅ [${elapsed}s] Login EXITOSO — redirigido a: ${currentUrl}`);
        success = true;
        break;
      }
    }

    // ¿Apareció "Escoja cómo desea ingresar"? (pantalla post-login para representantes)
    if (currentUrl.includes('CAutInicio.cgi')) {
      const content = await page.content().catch(() => '');
      const lower = content.toLowerCase();
      if (lower.includes('escoja') && lower.includes('cómo desea ingresar')) {
        console.log(`✅ [${elapsed}s] Pantalla "Escoja cómo desea ingresar" — login OK`);
        success = true;
        break;
      }
      // ¿Texto de error persistente tras 15s? Entonces el challenge falló
      if (elapsed > 15 && lower.includes('no se puede responder a sus requerimientos')) {
        console.log(`🛑 [${elapsed}s] Challenge fallido — error persistente en CAutInicio.cgi`);
        errorDetected = true;
        break;
      }
    }

    if (elapsed % 10 === 0 && elapsed > 0) {
      console.log(`   [${elapsed}s] esperando challenge...`);
    }
  }

  if (success) {
    await page.screenshot({ path: path.join(CAPT_DIR, 'puppeteer_login_ok.png') }).catch(() => {});
    const title = await page.title().catch(() => '?');
    console.log(`📋 Título: ${title}`);
    console.log('✅ LOGIN AUTOMÁTICO EXITOSO');
  } else {
    await page.screenshot({ path: path.join(CAPT_DIR, 'puppeteer_challenge_failed.png') }).catch(() => {});
    console.log('🛑 Login fallido — challenge F5 BIG-IP no superado');
    console.log(`   URL final: ${currentUrl}`);
  }

  await browser.close();
  try { fs.unlinkSync(CREDS_FILE); console.log('🧹 Creds temporales borrados.'); } catch (e) {}
})();
