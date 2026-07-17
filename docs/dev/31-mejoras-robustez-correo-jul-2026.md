# 31 · Mejoras de robustez y observabilidad del correo (jul-2026)

> **Estado (17-jul-2026):** ✅ Todo implementado, testeado (**175 tests en verde**) y **LIVE en
> producción** (verificado por `/health.version = 2026-07-17.1-avisos-multi-cc`). Este documento
> consolida las mejoras del sistema de correo hechas entre el **15 y el 17 de julio de 2026** y
> deja el **estado operativo final** de la Fase 1.
>
> **Decisión de negocio (GCP/Carlos):** el proyecto **se queda en la Fase 1** — *automatizar Notion
> + correos automáticos* (F29, RRHH, Tickets). Las otras fases del [`../ROADMAP.md`](../ROADMAP.md)
> (motor de cálculo, ingesta SII, auditoría, IA, BD especializada) quedan **para el futuro**. Por eso
> el foco fue dejar el correo lo más **robusto y autoexplicativo** posible, sin depender de devs.
>
> Continúa el [`27`](27-robustez-observabilidad-plan.md) (plan de robustez) y el
> [`30`](30-confirmacion-entrega-sendgrid.md) (confirmación de entrega).

---

## §0 · El incidente que lo disparó (15-jul-2026)

**Caso RENOFAT SPA:** el correo del F29 no salió y SendGrid respondió un `HTTP 400` críptico en
inglés: `"Does not contain a valid address" (field: personalizations.0.to.0.email)`. **Causa raíz:**
la celda **Email** de la fila en Notion tenía `8.568.094-3 / nicojuan2` (un RUT + usuario del SII
pegados en la columna equivocada), no un correo. Notion **no valida** esa columna, así que el dato
basura viajaba hasta SendGrid — que lo rechazaba, y de paso recibía ese dato sensible.

Un barrido completo de **Contable Junio** (194 filas, 51 con Email) encontró **2 celdas inválidas**
según la validación del backend: **RENOFAT** y **Hydroming** (esta con 3 correos apretados en una
sola celda). El incidente motivó las 5 mejoras de abajo.

---

## §1 · Las mejoras (5 + señal de deploy)

| # | Mejora | Archivo(s) | Commit |
|---|--------|-----------|:------:|
| 1 | **Validación de Email antes de SendGrid** | `email_sender.py` (`_validar_destinatarios`) | `1dd1c35` |
| 2 | **Reintento automático único ante rebote** | `app.py` (`_agendar_reintento`) | `0ecb516` |
| 3 | **Fallback F29 de Email por RUT a la base madre** | `notion_client.py` (`buscar_email_en_central`), `app.py`, `rrhh.py` | `46df756` |
| 4 | **Multi-destinatario en la celda Email (to + CC)** | `email_sender.py` (`parse_destinatarios`) | `f89858b` |
| 5 | **Avisos de error a 2 audiencias** | `diagnostico.py` (nuevo), `email_sender.py`, `alertas.py` | `fae5161` |
| — | **`/health.version` como señal de deploy** | `app.py` (`health`) | `af7cd6a` |

### 1.1 · Validación de Email antes de llamar a SendGrid
`email_sender._validar_destinatarios()` corta **antes** de SendGrid cualquier valor que no sea un
correo válido (un RUT, un usuario, texto suelto). Lanza un `ValueError` con un motivo claro en
español **sin incluir el valor de la celda** (los motivos van a los logs, política sin PII). Como
va dentro de `enviar()`, cubre **F29, RRHH y Tickets** de una vez. Antes, ese dato basura llegaba a
SendGrid y volvía un 400 en inglés.

### 1.2 · Reintento automático único ante rebote (bounce)
Extiende el [`30`](30-confirmacion-entrega-sendgrid.md). Ante el **primer** `bounce` de una fila, el
webhook agenda **un** reintento automático a los **10 min** (`REINTENTO_BOUNCE_S`, `threading.Timer`)
**sin alarmar al asesor todavía** — muchos rebotes son un hipo transitorio del DNS/MX del cliente
(caso real Mockenau: rebotó a las 18:23 por `unable to get mx info`, el reenvío 25 min después
entregó OK). Si el reintento **también** rebota, el segundo evento sí dispara el aviso. `dropped` no
se reintenta (SendGrid ya suprimió el envío). Estado en memoria del proceso (`_reintentos_hechos`).

### 1.3 · Fallback F29 de Email por RUT a la base madre
El handler **RRHH** ya recuperaba el Email por RUT desde la base madre (*General Customers Data*)
cuando la fila venía sin correo; ahora **F29 también**. Helper compartido
`notion_client.buscar_email_en_central(rut)` (**solo lectura** sobre la base sagrada); se eliminó la
copia duplicada de `rrhh.py`. Cierra los casos de filas con Email vacío cuyo correo **sí existe** en
la central (visto 15-jul: CONSTRUGLOBAL, Neurocirugía, NATALIA, ZOE se auto-sanan). Si la central
devuelve basura (ej. `"SOLO WATHSAPP"`), la validación (§1.1) la corta igual.

### 1.4 · Multi-destinatario en la celda Email (to + CC)
Pedido del usuario (caso Hydroming: el cliente quiere recibir en 3 direcciones). La celda Email
ahora acepta **varias direcciones** separadas por coma, espacio, `;` o `/`: la **1ª es el `to`** y el
resto van en **CC visible**. `parse_destinatarios()` se reutiliza en el **filtro anti-BCC** del
webhook, para que un `delivered`/`bounce` a **cualquiera** de las direcciones del cliente cuente
como evento legítimo (no se confunda con una copia BCC). SendGrid exige `to`/`cc`/`bcc` disjuntos →
se deduplica. Cubre F29, RRHH y Tickets.

### 1.5 · Avisos de error a 2 audiencias (el núcleo de la observabilidad)
Antes, un fallo mandaba **un** correo técnico único (asesor + admin en cc). Ahora el módulo nuevo
[`diagnostico.py`](../../notion_automation/diagnostico.py) (puro, testeable) **clasifica** el motivo
en **9 categorías** y `alertas.avisar_fallo_asesor` manda **dos correos a medida**:

- **Al asesor (contador, no dev):** `email_sender.enviar_aviso_asesor` — titular claro, si **lo
  puede resolver solo**, y pasos concretos en Notion. Sin tecnicismos, sin `page_id`, sin query.
- **Al dev (`ADMIN_ALERT_EMAIL`):** `email_sender.enviar_aviso_dev` — causa raíz técnica, detalle
  para depurar, y una **query lista para pegar en un chat con un LLM** (Claude) y resolverlo directo
  vía el MCP de Notion (fetch/update de la fila).

**Categorías:** `email_invalido`, `sin_email`, `bounce`, `sin_mes`, `remitente_no_verificado`,
`asesor_pendiente`, `config`, `sin_titulo`, `desconocido`. Los handlers y el webhook pasan
`flujo` + `page_id` (+ `extra` con `bounce_reason`/`ya_reintentado`) para enriquecer el diagnóstico.
Regla PII intacta: el correo del asesor no lleva la query ni el page_id; los motivos nunca incluyen
el valor de la celda Email.

> 🖼️ Vista previa de ambos correos (3 escenarios) y de las plantillas de Tickets: artifacts privados
> generados el 15-17 jul para revisión con Carlos.

### 1.6 · `/health.version` como señal de deploy
El campo `version` de `/health` estaba fijo en un valor viejo, así que no servía para verificar que
un deploy nuevo hubiera quedado vivo. Ahora se bumpea con cada tanda de cambios (hoy
`2026-07-17.1-avisos-multi-cc`): comparar `/health.version` confirma que Render tomó el último push.

---

## §2 · Estado operativo final (17-jul-2026)

Todos los cabos operativos del correo quedaron **cerrados y verificados en vivo** (`GET /health`):

| Cabo operativo | Estado |
|---|:---:|
| Último código en producción | ✅ `version = 2026-07-17.1-avisos-multi-cc` |
| **Autenticación de dominio** `inversoragcp.com` en SendGrid | ✅ (todas las cuentas `@inversoragcp.com` verificadas; sin *"via sendgrid.net"*) |
| **SendGrid Essentials** | ✅ **PAGADO** (sin riesgo de pausa al vencer el trial del 07-sep) |
| Todos los asesores activos | ✅ Sebastián, Carlos, Constanza, Matilde, Andrea |
| `ADMIN_ALERT_EMAIL` | ✅ configurada (`admin_alerts_configurados: 2`) |
| `WEBHOOK_SECRET` / `SENDGRID_WEBHOOK_TOKEN` | ✅ configurados |
| Render always-on (Starter $7) | ✅ sin cold-start |

**Lo único que queda (acción humana de GCP, no código):**
1. Conseguir los **correos reales** de **RENOFAT** y **STIVEN** (no existen en ninguna base).
2. **Feedback de Carlos** sobre las plantillas de Tickets (PDF enviado).
3. **Rotar las App Passwords viejas** ([`27`](27-robustez-observabilidad-plan.md) Fase 0) —
   higiene de baja prioridad; la nube usa SendGrid API, no SMTP, así que no afectan la operación.

---

## §3 · Tests

**175 tests en verde** (pytest, ~0.4s, sin llamadas reales). Nuevos/reescritos en esta tanda:
`test_diagnostico.py` (clasificador, 15 tests), `test_f29_central_lookup.py`, casos de
`TestValidarDestinatarios`/`TestParseDestinatarios`/`TestCC` en `test_puras.py` y
`test_sendgrid_webhook.py`, y la reescritura de `test_alertas.py` para los dos correos a medida.

> ⚠️ **Lección de seguridad (reforzada):** el clasificador de seguridad bloqueó **2 pushes** que
> llevaban PII real de clientes (correos/RUTs) dentro de archivos de test versionados. Regla: en
> tests y artifacts, **solo datos ficticios** (`example.com`, RUTs `11111111-1`).

---

**Anterior:** [`30-confirmacion-entrega-sendgrid.md`](30-confirmacion-entrega-sendgrid.md) ·
**Volver al** [`README`](README.md)
