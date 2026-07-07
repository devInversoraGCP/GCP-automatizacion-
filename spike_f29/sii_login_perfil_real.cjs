// sii_login_perfil_real.cjs — Login SII usando el perfil REAL de Chrome del usuario
// F5 BIG-IP detecta perfiles frescos/vacíos como bots. Usar el perfil real
// (cookies, historial, TLS fingerprint, extensiones) debería bypassar el WAF.
//
// REQUIERE: Chrome cerrado (no se puede usar el mismo perfil si ya está abierto)
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');
const os = require('os');

puppeteer.use(StealthPlugin());

const CREDS_FILE = path.join(__dirname, 'data', '_creds.json');
const URL_LOGIN = 'https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html';

// Perfil real de Chrome del usuario (Windows)
const USER_DATA_DIR = path.join(os.homedir(), 'AppData', 'Local', 'Google', 'Chrome', 'User Data');

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

(async () => {
  if (!fs.existsSync(USER_DATA_DIR)) {
    console.error(`❌ Perfil de Chrome no encontrado: ${USER_DATA_DIR}`);
    process.exit(1);
  }
  console.log(`📁 Usando perfil real: ${USER_DATA_DIR}`);

  const creds = JSON.parse(fs.readFileSync(CREDS_FILE, 'utf-8'));

  console.log('🚀 Lanzando Chrome con perfil REAL + StealthPlugin...');
  const browser = await puppeteer.launch({
    headless: false,  // visible (R6) — perfil real no funciona bien en headless
    userDataDir: USER_DATA_DIR,  // perfil real del usuario
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
      '--profile-directory=Default',  // usar el perfil Default
    ],
    defaultViewport: { width: 1280, height: 800 },
  });

  const page = await browser.newPage();

  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['es-CL', 'es', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
  });

  console.log('🌐 Navegando al login del SII...');
  await page.goto(URL_LOGIN, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await randomSleep(1500, 3000);

  try {
    await page.waitForSelector('#rutcntr', { timeout: 15000 });
  } catch (e) {
    console.log('⚠ Formulario no encontrado — quizá ya hay sesión activa');
    console.log(`   URL: ${page.url()}`);
    if (!page.url().includes('IngresoRutClave') && !page.url().includes('CAutInicio')) {
      console.log('✅ Sesión ya activa — dentro de Mi SII');
    }
    await sleep(10000);
    await browser.close();
    try { fs.unlinkSync(CREDS_FILE); } catch (e) {}
    return;
  }

  console.log('⌨️  Typing RUT + clave (humanizado)...');
  await typeHuman(page, '#rutcntr', creds.rut);
  await randomSleep(500, 1500);
  await typeHuman(page, '#clave', creds.clave);
  await randomSleep(800, 2000);

  console.log('🖱️  Click "Ingresar"...');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {}),
    page.click('#bt_ingresar'),
  ]);

  let currentUrl = page.url();
  console.log(`📍 URL post-click: ${currentUrl}`);
  console.log('⏳ Esperando resultado (60s)...');

  const startTime = Date.now();
  let success = false;

  while (Date.now() - startTime < 60000) {
    await sleep(2000);
    const newUrl = page.url();
    const elapsed = Math.floor((Date.now() - startTime) / 1000);

    if (newUrl !== currentUrl) {
      console.log(`   [${elapsed}s] URL cambió: ${newUrl}`);
      currentUrl = newUrl;
    }

    // ¿URL cambió fuera de CAutInicio.cgi y login?
    if (!currentUrl.includes('CAutInicio.cgi') && !currentUrl.includes('IngresoRutClave')) {
      const content = await page.content().catch(() => '');
      if (!content.toLowerCase().includes('no se puede responder a sus requerimientos')) {
        console.log(`✅ [${elapsed}s] Login EXITOSO — URL: ${currentUrl}`);
        success = true;
        break;
      }
    }

    // ¿Escoja cómo ingresar?
    if (currentUrl.includes('CAutInicio.cgi')) {
      const content = await page.content().catch(() => '');
      const lower = content.toLowerCase();
      if (lower.includes('escoja') && lower.includes('cómo desea ingresar')) {
        console.log(`✅ [${elapsed}s] Pantalla "Escoja cómo ingresar" — login OK`);
        success = true;
        break;
      }
      if (elapsed > 20 && lower.includes('no se puede responder a sus requerimientos')) {
        console.log(`🛑 [${elapsed}s] Error persistente — WAF bloqueando`);
        break;
      }
    }

    if (elapsed % 10 === 0 && elapsed > 0) {
      console.log(`   [${elapsed}s] esperando...`);
    }
  }

  if (success) {
    console.log('✅ LOGIN AUTOMÁTICO EXITOSO con perfil real + StealthPlugin');
  } else {
    console.log('🛑 Login fallido');
    console.log(`   URL final: ${currentUrl}`);
  }

  console.log('\n⏸  15s para inspección...');
  await sleep(15000);
  await browser.close();
  try { fs.unlinkSync(CREDS_FILE); console.log('🧹 Creds borrados.'); } catch (e) {}
})();
