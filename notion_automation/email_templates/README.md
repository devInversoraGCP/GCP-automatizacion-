# Plantilla del correo F29 — variables y variantes

Correo base que el botón **"Enviar F29"** dispara para cada cliente (ver
[`../../docs/dev/23-automatizacion-notion-contable-correo.md`](../../docs/dev/23-automatizacion-notion-contable-correo.md)).
El backend (`email_sender.py`) carga [`f29_email.html`](f29_email.html) (y
[`f29_email.txt`](f29_email.txt) como respaldo) y reemplaza los marcadores `{{...}}`.

**Se personaliza por cliente y por mes:** los datos salen de la fila de la página Contable, leídos
en memoria por el backend. **Nada sensible viaja en el webhook** (solo el `page_id`).

## Asunto del correo
**`Asesoría Honorario`** (fijo, definido en `email_sender.py`). *(Feedback del usuario: el título
del correo es simplemente "Asesoría Honorario".)*

## Variables

| Marcador | De dónde sale | Ejemplo |
|---|---|---|
| `{{logo_url}}` | config del backend — **URL pública** del logo GCP | `https://gcp.cl/logo.png` |
| `{{nombre_cliente}}` | columna `Customers` (title) | `Servicios Oporto` |
| `{{periodo}}` | columna `Month` (text) | `Mayo 2026` |
| `{{monto}}` | columna `Impuestos` (number) → CLP | `$260.143` |
| `{{titulo_resultado}}` / `{{mensaje_resultado}}` | derivados del signo del monto (ver variantes) | `Total a pagar` |
| `{{bloque_fecha_limite}}` / `{{linea_fecha_limite}}` | **calculado** desde `Month` (ver §Fecha límite) | `lunes 22 de junio de 2026` |
| `{{bloque_honorarios}}` / `{{linea_honorarios}}` | columna `Honorarios Pendientes` — **opcional** (incluye datos de transferencia) | `$85.000` + banco |
| `{{bloque_info_adicional}}` / `{{linea_info_adicional}}` | columna `Info Adicional` (text) — **opcional y flexible** | remanente u otro |
| `{{asesor}}` | columna `Adviser Accounting` o valor por defecto | `Equipo GCP` |
| `{{contacto_email}}` | config del backend (correo de GCP) | `contacto@gcp.cl` |

## Logo (encabezado)
El correo usa **`LOGO-GCP.png`** (raíz del repo) sobre **banda blanca** con línea navy de acento
(el logo es oscuro y no se ve sobre navy). ⚠️ Los clientes de correo (Gmail, etc.) **bloquean los
`data:` URIs**; el logo debe ir por **URL hospedada** (`{{logo_url}}`) o adjuntarse **inline por
CID** (SendGrid soporta `ContentId`). En la vista previa (`preview-correo-f29.html`) sí va
incrustado como base64 porque los Artifacts permiten data URIs.

## Formateo del monto (`{{monto}}`)
Peso chileno: separador de miles `.`, prefijo `$` (`260143` → `$260.143`). Función `clp()`.

## Variantes según el resultado del F29 (columna `Impuestos`)
| Caso | Condición | `titulo_resultado` | `mensaje_resultado` |
|---|---|---|---|
| **Con pago** | `Impuestos` > 0 | `Total a pagar` | `Corresponde al Formulario 29 del período {{periodo}}.` |
| **Sin movimiento** | `Impuestos` = 0 / vacío | `Declaración sin pago` | `Su Formulario 29 del período {{periodo}} se declara sin pago este mes.` |
| **Saldo a favor** *(futuro)* | `Impuestos` < 0 | `Saldo a favor` | `Este mes no debe pagar; el saldo a favor se arrastra al período siguiente.` |

## Fecha límite de pago (`{{bloque_fecha_limite}}` / `{{linea_fecha_limite}}`)
**Regla (usuario, jul-2026):** plazo = **día 20 del mes SIGUIENTE** al período; si ese día **no es
hábil** (fin de semana o **feriado chileno**), se traslada al **siguiente día hábil**.
*(Ej.: Mayo 2026 → 20-jun sábado, 21-jun domingo y feriado → **lunes 22 de junio de 2026**.)*
Feriados: nacionales, desde `date.nager.at/api/v3/PublicHolidays/{año}/CL` (la API del gobierno
`apis.digital.gob.cl` está **deprecada**), con lista fija de respaldo revisable por año. Ver
`fecha_limite()` y `FERIADOS_CL` en `docs/dev/23` §5.2.b.

**HTML de `{{bloque_fecha_limite}}`** (solo la fecha, sin texto entre paréntesis — feedback usuario):
```html
<p style="margin:0 0 18px 0;font-size:14px;line-height:1.6;color:#3a4658;">
  <b>Fecha límite de pago:</b> lunes 22 de junio de 2026.
</p>
```
**Texto** (`{{linea_fecha_limite}}`): `Fecha límite de pago: lunes 22 de junio de 2026.`

## Honorarios pendientes + datos de transferencia (`{{bloque_honorarios}}`)
**Regla (Carlos, jul-2026):** informar los **honorarios de asesoría (GCP) pendientes del mes** —
lo que el cliente aún debe a GCP por el servicio. **Distinto del impuesto del F29** (uno al SII,
otro a GCP). Si el cliente **debe honorarios**, incluir los **datos bancarios para transferir**.
- Sale de la columna **`Honorarios Pendientes`** (number). Solo si > 0 se muestra el bloque.
- Los datos bancarios son fijos (cuenta de GCP para recibir pagos).

**HTML de `{{bloque_honorarios}}`** cuando hay honorarios > 0:
```html
<div style="margin:0 0 18px 0;background:#fff8ec;border:1px solid #f2e2bf;border-left:4px solid #E7A100;border-radius:10px;padding:14px 18px;">
  <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9a7400;margin-bottom:3px;">Honorarios de asesoría · pendientes</div>
  <div style="font-size:14px;color:#3a4658;line-height:1.55;">Además, tiene <b>honorarios de asesoría pendientes por $85.000</b> correspondientes a nuestros servicios del mes. (Independiente del impuesto del F29.)</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f2e2bf;font-size:13px;color:#3a4658;line-height:1.7;">
    <b>Datos para la transferencia:</b><br>
    Banco Santander · Cuenta Corriente<br>
    N° 0-000-8577678-9<br>
    RUT: 76.976.672-3<br>
    Razón Social: Inversora GCP Ltda
  </div>
</div>
```
**Texto** (`{{linea_honorarios}}`): `Honorarios de asesoría pendientes: $85.000 (independiente del impuesto del F29). Transferir a: Banco Santander, Cuenta Corriente N° 0-000-8577678-9, RUT 76.976.672-3, Razón Social Inversora GCP Ltda.`

## Información adicional — flexible y opcional (`{{bloque_info_adicional}}`)
**Regla (usuario, jul-2026):** este bloque es **variable**: **puede no aparecer** (si la celda está
vacía) y **no siempre es el remanente** — puede ser otra información. Por eso es un **texto libre**.
- Sale de la columna **`Info Adicional`** (text) de Contable. Si está vacía → el bloque no aparece.
- GCP escribe ahí lo que quiera (p. ej. "A su favor queda un remanente de $417.798 que se arrastra
  al próximo período", u otra nota). El correo lo muestra **verbatim**.

**HTML de `{{bloque_info_adicional}}`** cuando la columna tiene contenido:
```html
<div style="margin:0 0 18px 0;background:#f4f6fa;border:1px solid #dfe5ee;border-radius:10px;padding:14px 18px;">
  <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#5a6b82;margin-bottom:3px;">Información adicional</div>
  <div style="font-size:14px;color:#3a4658;line-height:1.55;">{{info_adicional_texto}}</div>
</div>
```
**Texto** (`{{linea_info_adicional}}`): `Información adicional: {{info_adicional_texto}}`

## Columnas nuevas a crear en Contable (para que el correo funcione)
Carlos autorizó agregar en Notion lo necesario:

| Columna | Tipo | Para qué |
|---|---|---|
| `Enviar F29` | button | dispara el correo (webhook) |
| `Honorarios Pendientes` | number | alimenta `{{bloque_honorarios}}` (con datos de transferencia) |
| `Info Adicional` | text | alimenta `{{bloque_info_adicional}}` (flexible; remanente u otro) |

Se reutilizan `Customers`, `Email`, `Month`, `Impuestos`, `Status`. La **fecha límite no necesita
columna** (se calcula desde `Month`). ⚠️ Contable es una base **real** (no la sandbox): agregar
columnas es aditivo y reversible, pero se hace con **backup + confirmación** (reglas de oro).

## Notas de diseño (email-safe)
- Layout con **tablas** y **estilos inline** (Gmail/Outlook ignoran `<style>` y CSS externo).
- Ancho máx. **600px**, fuentes del sistema, imágenes solo por URL hospedada.
- Colores de la identidad de la presentación (`#0B1F3A`). Ajustar `{{contacto_email}}` al correo real de GCP.
