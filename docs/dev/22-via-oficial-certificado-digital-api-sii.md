# 22 · Vía oficial: certificado digital + API del SII (100% automática, nativa de nube)

> **Pregunta que responde:** ¿existe una forma de automatizar al **100%** la extracción de datos
> del SII (RCV, honorarios) **sin login por navegador**, que corra en un **backend en la nube 24/7**
> y que **no dependa de vencer el anti-bot F5** que bloqueó el spike ([`21`](21-resultado-spike-f29.md))?
>
> **Veredicto: SÍ.** El SII expone una **puerta oficial máquina-a-máquina** autenticada por
> **certificado digital** (no por Clave Tributaria en el navegador). Es HTTP + firma criptográfica
> pura: sin navegador, sin sensor JS, sin F5. Es exactamente la arquitectura que usa **todo** el
> software de facturación chileno (LibreDTE, SimpleAPI, BaseAPI, etc.) y es **nativa de nube**.
>
> **Estado:** 🔬 investigación (07-jul-2026) validada contra fuentes oficiales y open-source.
> Requiere una **decisión de negocio** (certificados/delegación — §5) antes de implementar.

---

## 1 · Por qué esta vía y no vencer a F5

| | Camino A · Navegador anti-F5 | **Camino B · Certificado (este doc)** |
|---|---|---|
| Login | Automatiza el formulario Clave Tributaria → choca con F5 Shape | **No usa ese login.** Autentica por certificado en otra puerta |
| Tecnología | Navegador headless + evasión | **HTTP + firma XML/criptográfica** |
| Nube 24/7 | ❌ peor aún: IP datacenter + headless = más detectable | ✅ **ideal** — sin GUI, sin display, sin navegador |
| Robustez | Frágil: se rompe con cada update de F5 | **Sancionada por el SII** — estable en el tiempo |
| Veredicto | Carrera armamentista perdida | **La base correcta para producción** |

> 🔑 **Idea central:** el anti-bot F5 vive en la puerta de **Clave Tributaria** (`zeusr.sii.cl`,
> navegador, humanos). El SII tiene **otra puerta para máquinas** (`palena.sii.cl` + servicios
> `www4`) autenticada por **certificado digital**, que da un **token de sesión** con el que se
> consultan los datos por API. No hay que engañar a nada: es la entrada diseñada para esto.

---

## 2 · Arquitectura 100% automática (de dónde sale cada variable del F29)

Cada dato del cálculo P1→P6 ([`17`](17-especificacion-literal-calculo-f29.md)) tiene una fuente
programática — **ninguna requiere navegador**:

| Variable | Casilla | Fuente programática | Estado |
|---|---|---|---|
| P1 débito · P2 crédito · BI (neto+exento) | 502/520/62 | **API RCV** (`consdcvinternetui/services/data/...`) | ✅ confirmado |
| ret. honorarios | 151 | **API BHE** (boletas de honorarios electrónicas, `bolcoreinternetui/api`) | 🟡 a verificar endpoint |
| remanente mes anterior | 504 | **El motor lo arrastra solo** (= `77` del mes anterior, ya calculado) — no necesita llamar al SII | ✅ diseño |
| tasa PPM | 115 | **Config por cliente en Notion** (es un atributo estable del cliente) o API F29 | 🟡 decisión |
| impuesto único | 48 | **Notion RRHH** (ya integrado, [`18`](18-integracion-impuesto-unico-imposiciones.md)) | ✅ hecho |

> 💡 **Consecuencia importante:** la parte más crítica (P1/P2/BI del RCV) es **API confirmada**.
> El remanente (504) **no requiere consultar la propuesta del F29** — el motor lo trae del mes
> anterior. La tasa PPM (115) es un dato estable por cliente que puede vivir en Notion. Es decir:
> **el modelo completo se puede resolver sin abrir jamás la propuesta del F29 en el navegador**,
> que era justo el paso que exigía el flujo anti-F5. Esto **simplifica** el proyecto.

---

## 3 · El flujo de autenticación (semilla → firma → token)

Estándar del SII, idéntico al que usa LibreDTE y todo el ecosistema DTE:

```text
1. getSeed()        → pide una SEMILLA (string, ej. "0123456789")
                      GET/POST SOAP a  palena.sii.cl/DTEWS/CrSeed.jws
2. firmar(semilla)  → firma la semilla con la CLAVE PRIVADA del certificado digital (.pfx/.p12)
                      → produce un XML firmado (XML-DSig / RSA-SHA1)
3. getToken(xml)    → cambia la semilla firmada por un TOKEN de sesión
                      POST SOAP a  palena.sii.cl/DTEWS/GetTokenFromSeed.jws
4. usar el TOKEN    → como cookie "TOKEN" en las llamadas a los servicios de datos (RCV, etc.)
                      el token se cachea y se reutiliza hasta que expira
```

- **Producción** = `palena.sii.cl` · **Certificación/pruebas** = `maullin.sii.cl` (mismo flujo,
  ambiente de test — ideal para desarrollar sin tocar datos reales).
- La firma se hace **en el backend** con la clave privada del certificado. No hay interacción humana.

---

## 4 · La API del RCV (lo confirmado)

El Registro de Compras y Ventas expone servicios JSON internos que el propio portal usa:

| Servicio | Endpoint (base `https://www4.sii.cl/consdcvinternetui/services/data/facadeService/`) | Devuelve |
|---|---|---|
| Resumen compras | `getResumenCompra` (nombre a confirmar en vivo) | totales de compras del período |
| Detalle compras | **`getDetalleCompraExport`** (confirmado en fuentes) | filas de compra (IVA recuperable, etc.) |
| Resumen/Detalle ventas | equivalentes de venta | filas de venta (Monto IVA, Neto, Exento) |

- **Método:** `POST` con cuerpo **JSON** que incluye metadata con un `conversationId` = el TOKEN.
- **Autenticación:** header **`Cookie: TOKEN=<token>`** obtenido en §3.
- **Formato:** JSON (algunos endpoints exportan CSV). Los nombres de campo son los del RCV
  (`MntIVA`, `MntNeto`, `MntExento`, `MntIVARecuperable`, `TpoDoc`, `RUTDoc`…) — mismos que ya
  documenta [`17`](17-especificacion-literal-calculo-f29.md) §3.
- **Patrón de nube probado:** existe una solución .NET open-source que guarda el **PFX en Azure
  Blob Storage** y llama al RCV con `HttpClient` autenticado (ver Fuentes). Es exactamente el
  patrón de un backend 24/7: certificado en almacén de secretos + cliente HTTP headless.

> ⚠️ **A verificar en implementación** (no asumir de memoria): los nombres exactos de los métodos
> del `facadeService` para ventas y resumen, la forma exacta del body JSON, y si el token de
> `palena` se acepta directamente como cookie en `www4` o requiere un paso puente. Se confirma
> con una llamada real en ambiente de **certificación (maullin)** — sin riesgo.

---

## 5 · El prerrequisito de NEGOCIO (no es código) — 🧑‍💼 para Carlos/GCP

El certificado digital del SII es **personal**: pertenece a un **RUT de persona natural**, y esa
persona debe estar registrada como **representante/usuario autorizado** de la empresa cliente, con
permiso para consultar su RCV. Esto abre dos modelos:

| Modelo | Cómo funciona | Implica |
|---|---|---|
| **A · Un certificado por cliente** | Cada cliente entrega su propio certificado digital `.pfx` | Gestionar 331 certificados y sus claves. Inviable a escala. |
| **B · Certificado de GCP + delegación** ✅ | El cliente autoriza en el SII al RUT de GCP como **representante electrónico**; GCP usa **un solo certificado** (el suyo) para operar por todos | Un trámite de delegación por cliente (una vez), luego 1 credencial cubre a los 331 |

> **El modelo B es como operan las asesorías a escala en Chile.** Es la vía sostenible.

**✅ GATE DE NEGOCIO RESUELTO (07-jul-2026, confirmado por el creador):**
1. ✅ **GCP tiene certificado digital propio del SII.**
2. ✅ **Los clientes ya delegaron en GCP como representante electrónico.**
3. ⇒ Se adopta el **modelo B**: **un solo certificado (el de GCP)** opera por todos los clientes vía delegación. No hace falta recolectar certificados por cliente.

**Único pendiente (técnico, no de negocio):** confirmar con GCP el **formato** del certificado —
archivo `.pfx`/`.p12` (ideal, va directo a la nube) o **token físico/eToken** (requiere puente o
exportación). No está instalado en la máquina del creador (verificado 07-jul: solo hay un cert de
Windows/Azure AD). **Pregunta a GCP:** *"El certificado del SII, ¿es un archivo `.pfx`/`.p12` que
descargaron, o un dispositivo físico? ¿Nos lo pueden entregar de forma segura?"*

> 📌 Nota sobre lo que hoy hay en Notion: la base guarda **RUT + Clave SII**. Esta vía usa una
> credencial **distinta** (el certificado `.pfx` + su clave). La Clave SII deja de ser necesaria
> para la extracción si se adopta el certificado — un dato sensible menos que manejar por cliente.

---

## 6 · Seguridad y despliegue en nube

- 🔒 **El certificado `.pfx` y su clave** se guardan en un **gestor de secretos** del proveedor
  (Azure Key Vault / AWS Secrets Manager / GCP Secret Manager), **nunca** en el repo ni en Notion.
  Patrón confirmado: PFX en almacenamiento cifrado, cargado en memoria por el backend al firmar.
- 🔒 Regla de oro vigente ([`AGENTS.md`](../../AGENTS.md)): credenciales solo en memoria, jamás en
  logs ni outputs. Aplica igual al certificado.
- ☁️ **Sin navegador** ⇒ el backend puede ser un contenedor mínimo (sin Chromium, sin display).
  Corre en cualquier VM/función/contenedor 24/7. Mucho más liviano y barato que un navegador headless.
- ⚠️ **IP:** las llamadas salen de la IP del datacenter. A diferencia del navegador anti-F5, aquí
  **no importa** (no hay bot-defense en esta puerta). Aun así, conviene una IP estable/egress fija
  por si el SII aplica rate-limiting por origen.
- ⏱️ **Token cacheado** y renovado al expirar (el flujo §3 es barato de repetir).

---

## 7 · Qué queda confirmado y qué falta verificar

**✅ Confirmado (fuentes oficiales + open-source en producción):**
- El SII autentica por certificado vía semilla→firma→token (manual oficial de Autenticación Automática).
- El RCV tiene API JSON interna (`getDetalleCompraExport` y familia) autenticada por cookie TOKEN.
- El patrón corre headless en la nube con el PFX en un blob/secret store (implementación .NET real).
- El modelo de **representación electrónica** existe y es oficial (ChileAtiende).

**🟡 A verificar antes/durante la implementación (en ambiente maullin, sin riesgo):**
- Nombres exactos de los métodos `facadeService` para **ventas** y **resumen** (los de compra están).
- Si el token de `palena` sirve tal cual como cookie en `www4/consdcvinternetui` o hay paso puente.
- Endpoint real de la **API de boletas de honorarios** (casilla 151) — apareció `www4c.sii.cl/bolcoreinternetui/api`.
- Si la **propuesta del F29** (504/115) tiene API — aunque §2 muestra que **probablemente no se necesita**.

---

## 8 · Recomendación y próximos pasos

1. **Adoptar el Camino B (certificado) como la arquitectura de producción.** Cerrar el intento de
   vencer F5 en el navegador salvo como plan de contingencia puntual. Registrar como decisión
   **D25** en [`05`](05-decisiones-y-preguntas.md).
2. **Consultar a Carlos** las 3 preguntas del §5 (certificado GCP + delegación). Es el gate de negocio.
3. **Prototipo de autenticación en `maullin` (certificación):** implementar semilla→firma→token con
   un certificado de prueba y hacer **una** llamada real al RCV. Valida toda la cadena sin tocar
   datos productivos. Es el nuevo "spike", ahora por la vía correcta.
4. **Conectar al motor:** `motor_f29.py` ya está listo para consumir P1/P2/BI ([`21`](21-resultado-spike-f29.md) §2).
5. Actualizar el flujo de datos ([`07`](07-flujo-de-datos.md)) y la presentación (el paso "Robot al
   SII" pasa a ser "Consulta API con certificado" — más simple y honesto).

---

## Fuentes

- [SII · Manual de Autenticación Automática (OI2007_AUTAUTOM)](https://www.sii.cl/factura_electronica/factura_mercado/autenticacion.pdf) — flujo semilla/token oficial.
- [SII · Certificado Digital](https://www.sii.cl/servicios_online/1039-certificado_digital-1182.html)
- [SII · Registro de Compras y Ventas](https://www.sii.cl/servicios_online/1039-3256.html)
- [LibreDTE · Inicio de sesión con certificado digital](https://www.libredte.cl/docs/procesos-sii/iniciar-sesion-con-certificado-digital) — autenticación por certificado (no clave).
- [LibreDTE · AuthenticateJob (semilla→token, cacheo)](https://lib-core.docs.libredte.cl/classes/libredte-lib-Core-Package-Billing-Component-Integration-Worker-SiiLazy-Job-AuthenticateJob.html)
- [sergioocode/Sii.RegistroCompraVenta](https://github.com/sergioocode/Sii.RegistroCompraVenta) — RCV con **PFX en Azure Blob Storage** (patrón de nube).
- [Recuperación Información RCV — endpoint `getDetalleCompraExport`](https://lenguajedemaquinas.blogspot.com/2018/03/recuperacion-informacion-registro.html)
- [ChileAtiende · Representación electrónica de otro contribuyente](https://www.chileatiende.gob.cl/fichas/3241-representacion-electronica-de-otro-contribuyente) — modelo de delegación.
- [SII · API BHE (boletas de honorarios)](https://www4c.sii.cl/bolcoreinternetui/api/) — casilla 151.

---

**Anterior:** [`21-resultado-spike-f29.md`](21-resultado-spike-f29.md) · **Volver al** [`README`](README.md)
