# 30 · Rotación de Mes con Reset Automático

> **Estado (13-jul-2026):** ✅ **Fases 1 y 2 implementadas** (endpoint `/reset-mes`
> para Contable + 15 tests, suite completa 100/100 en verde). Pendiente: Fase 3
> (RRHH/Tickets), crear el botón + columna en Notion (Cambios 2 y 3) y prueba E2E.
> Ver §"Implementación real" abajo para los ajustes respecto al plan original.
>
> **Objetivo:** Resolver la paradoja de la rotación (doc 28 §13.d) y automatizar
> el reset de datos operativos al cambiar de mes.

---

## Contexto para LLM

### Qué es AuditAI

AuditAI es un asistente contable que **lee datos de Notion, calcula el Formulario 29 del SII (Chile) y lo audita**. El sistema está compuesto por:

1. **Backend Flask** (`notion_automation/app.py`) — recibe webhooks de botones en Notion, lee filas de bases de datos, envía correos electrónicos y escribe de vuelta el estado en Notion.

2. **Base de datos Notion "Contable"** — cada mes tiene una base "Contable <Mes>" con ~330 filas (clientes). Cada fila tiene: nombre, RUT, clave SII, email, asesor, impuestos, estado, botón para enviar correo.

3. **Integración Notion** — una conexión (connection) que permite al backend leer/escribir en las bases de datos via API.

### El problema de la rotación

Cada mes, las bases deben "rotar" al mes siguiente. El problema original (doc 28 §13.d) era:

- **Duplicar via UI** → copia el botón pero NO la integración → la base queda huérfana
- **Crear via API** → la integración tiene acceso pero NO copia el botón configurado

### La solución del usuario (decisión final)

La base original **NUNCA se mueve**. El flujo es:

1. **Duplicar** la base original → queda como copia de seguridad "(1)"
2. **Renombrar** la base original al mes nuevo (ej: "Contable Junio" → "Contable Julio")
3. **Resetear** los datos operativos via botón "Reset Mes"

Esto resuelve la paradoja porque la integración se mantiene en la base original.

### Arquitectura actual del backend

```
notion_automation/
├── app.py                    # Flask backend, endpoints principales
├── notion_client.py          # Cliente API de Notion (DS_CONTABLES, find_page_by_rut, derivar_month_desde_base)
├── email_sender.py           # Envío de correos via SMTP
├── alertas.py                # Notificaciones de errores
├── handlers/
│   ├── rrhh.py               # Handler para correos RRHH
│   └── tickets.py            # Handler para correos de Tickets
├── email_templates/
│   ├── f29_email.html         # Plantilla correo F29
│   ├── rrhh_email.html        # Plantilla correo RRHH
│   └── tickets_*.html         # Plantillas Tickets
└── tests/
    ├── test_cambio_mes.py     # Tests de rotación (find_page_by_rut)
    └── test_mes_titulo_prioridad.py  # Tests de prioridad del título
```

### Flujo actual del webhook F29

```
Botón "Enviar Correo F29" en Notion
    ↓ POST /enviar-f29
    ↓ body: {"source": {"page_id": "..."}, "data": {"Rut": "...", "Email": "..."}}
    ↓
app.py: validar secreto → extraer page_id → dedup → _procesar_page(page_id)
    ↓
_procesar_page:
    1. nc.get_page(page_id) → lee la fila
    2. nc.derivar_month_desde_base(page) → "Julio 2026" (desde título de la base)
    3. es.enviar(...) → envía correo
    4. nc.update_props(page_id, {Status: "1) Enviado y Pendiente", Fecha Envío: now})
```

### Propiedades de la base Contable

**Estáticas (NUNCA se tocan):**
- `Customers` (title) — nombre del cliente
- `Rut` (rich_text) — RUT del cliente
- `Clave SII` (rich_text) — contraseña del SII
- `Email` (email) — correo del cliente
- `CRM` (select) — campo CRM
- `Adviser Accounting` (people) — asesor asignado
- `Actividad Econ` (select) — actividad económica
- `Reportabilidad` (select) — reportabilidad
- `datos socio` (rich_text) — datos del socio
- `Place` (unknown) — lugar
- `Adjuntos` (files) — PDFs adjuntos
- `Mensaje Adjuntos` (rich_text) — nota sobre adjuntos

**Dinámicos (se resetean cada mes):**
- `Month` (rich_text) — mes actual (ej: "Junio 2026")
- `Impuestos` (number) — monto del F29
- `Status` (status) — estado del proceso
- `Ventas` (checkbox) — flag de ventas
- `Compras` (checkbox) — flag de compras
- `Pre-Imptos` (checkbox) — flag de pre-impuestos
- `PreImp` (checkbox) — flag de pre-imp
- `ARec` (status) — estado de a recategorizar
- `Control Solicitudes` (status) — estado de control
- `emision de boletas` (status) — estado de boletas
- `solicitud/informe /boletas` (status) — estado de solicitud
- `Honorarios Pendientes` (number) — honorarios del mes
- `Valor-Info adicional` (number) — valor info adicional
- `Motivo-Info adicional` (rich_text) — motivo info adicional
- `Fecha Envío` (date) — fecha de envío del correo

**Especial:**
- `Enviar Correo F29` (button) — botón que dispara el webhook
- `Confirmar Reset` (checkbox) — **NUEVO** — safety switch para el reset

---

## Plan de Implementación

### Cambio 1: Endpoint `/reset-mes` en `app.py`

**Descripción:** Nuevo endpoint POST que recibe un webhook del botón "Reset Mes" y resetea todas las filas de la base.

**Endpoint:** `POST /reset-mes`

**Payload esperado:**
```json
{
  "tipo": "contable",
  "database_id": "39612147-b3ea-80e7-98e6-dbe3de45b76e"
}
```

**Lógica:**
1. Validar secreto `X-AuditAI-Secret`
2. Extraer `tipo` y `database_id` del payload
3. Verificar que `tipo` sea válido ("contable", "rrhh", "tickets")
4. Query a la base: obtener TODAS las filas (paginación)
5. Para cada fila:
   - Leer propiedades actuales
   - Verificar si el checkbox "Confirmar Reset" está marcado (en la fila ZZ_TEST o en una fila de control)
   - Si NO está marcado → rechazar con error "Marcá el checkbox Confirmar Reset primero"
   - Si ESTÁ marcado → aplicar reset de campos dinámicos
6. After reset: desmarcar checkbox "Confirmar Reset"
7. Responder con conteo de filas reseteadas

**Campos a resetear por tipo:**

```python
RESET_CONTABLE = {
    "Month": None,
    "Impuestos": None,
    "Status": {"status": {"name": "sin empezar"}},
    "Ventas": {"checkbox": False},
    "Compras": {"checkbox": False},
    "Pre-Imptos": {"checkbox": False},
    "PreImp": {"checkbox": False},
    "ARec": {"status": {"name": "sin empezar"}},
    "Control Solicitudes": {"status": {"name": "sin empezar"}},
    "emision de boletas": {"status": {"name": "sin empezar"}},
    "solicitud/informe /boletas": {"status": {"name": "sin empezar"}},
    "Honorarios Pendientes": None,
    "Valor-Info adicional": None,
    "Motivo-Info adicional": None,
    "Fecha Envío": None,
    "Confirmar Reset": {"checkbox": False},
}

RESET_RRHH = {
    # Definir según esquema de RRHH
}

RESET_TICKETS = {
    # Definir según esquema de Tickets
}
```

**Código pseudofuncional:**
```python
@app.post("/reset-mes")
def reset_mes():
    _validar_secreto()
    data = request.get_json(force=True, silent=True) or {}
    
    tipo = data.get("tipo", "")
    db_id = data.get("database_id", "")
    
    if tipo not in ("contable", "rrhh", "tickets"):
        abort(400, f"tipo desconocido: {tipo}")
    if not db_id:
        abort(400, "database_id requerido")
    
    # Definir campos a resetear según tipo
    campos_reset = RESET_CONTABLE if tipo == "contable" else RESET_RRHH if tipo == "rrhh" else RESET_TICKETS
    
    # Query todas las filas
    filas = nc.query_data_source(db_id, {"page_size": 100})
    
    # Verificar checkbox de confirmación en fila de prueba
    zz_test = next((f for f in filas if "ZZ_TEST" in nc.plain(f["properties"].get("Customers", {}))), None)
    if zz_test:
        props_test = zz_test["properties"]
        confirmado = props_test.get("Confirmar Reset", {}).get("checkbox", False)
        if not confirmado:
            abort(400, "Marcá el checkbox 'Confirmar Reset' en la fila ZZ_TEST primero")
    
    # Resetear cada fila
    reseteadas = 0
    for fila in filas:
        page_id = fila["id"]
        updates = {}
        for campo, valor in campos_reset.items():
            if campo in fila["properties"]:
                if valor is None:
                    updates[campo] = None  # limpiar
                else:
                    updates[campo] = valor
        if updates:
            nc.update_props(page_id, updates)
            reseteadas += 1
    
    log.info("reset-mes completado · tipo=%s · filas_reseteadas=%d", tipo, reseteadas)
    return {"ok": True, "tipo": tipo, "filas_reseteadas": reseteadas}, 200
```

---

### Cambio 2: Nueva columna "Confirmar Reset" en cada base

**Tipo en Notion:** Checkbox

**Propósito:** Safety switch — sin marcarlo, el botón de reset no hace nada.

**Ubicación recomendada:** Junto al botón "Reset Mes" en la UI.

**Flujo:**
1. Usuario marca checkbox "Confirmar Reset" en la fila ZZ_TEST
2. Usuario aprieta botón "Reset Mes"
3. Backend verifica checkbox → resetea → desmarca checkbox

---

### Cambio 3: Botones "Reset Mes" en Notion (UI)

Los botones se crean **manualmente** en la UI de Notion (la API no permite crear botones configurados).

> ⚠️ **Ajuste (13-jul-2026, al configurar el botón real):** el "Send webhook" de Notion
> **NO permite configurar el body** (Notion manda automáticamente los datos de la fila).
> `tipo` y `database_id` viajan en **headers custom** (`X-Reset-Tipo`, `X-Reset-DB`);
> el backend también los acepta por body como fallback (curl/tests).

**Configuración del botón (3 headers custom):**

| Campo | Valor |
|---|---|
| Label | "Reset Mes" |
| Action | "Send webhook" |
| URL | `https://auditai-backend-gubv.onrender.com/reset-mes` |
| Header 1 | `X-AuditAI-Secret: <WEBHOOK_SECRET>` |
| Header 2 | `X-Reset-Tipo: <tipo>` |
| Header 3 | `X-Reset-DB: <database_id>` |

**Por base:**

| Base | Header `X-Reset-Tipo` | Header `X-Reset-DB` |
|---|---|---|
| Contable Junio | `contable` | `39612147-b3ea-80e7-98e6-dbe3de45b76e` |
| RRHH JUNIO 2026 | `rrhh` | `38712147-b3ea-80f9-9484-e0ad99c94a26` |
| Tickets - Servicios | `tickets` | `9d312147-b3ea-83bf-b111-877c7b24db75` |

---

### Cambio 4: Tests

**Archivo nuevo:** `notion_automation/tests/test_reset_mes.py`

**Tests:**

1. **`test_reset_preserva_campos_estaticos`**
   - Mock: fila con Customers="Test", Rut="12345", Email="test@test.com"
   - Ejecutar reset
   - Verificar: Customers, Rut, Email intactos

2. **`test_reset_limpia_campos_dinamicos`**
   - Mock: fila con Impuestos=1000, Status="1) Enviado y Pendiente"
   - Ejecutar reset
   - Verificar: Impuestos=None, Status="sin empezar"

3. **`test_reset_sin_checkbox_rechaza`**
   - Mock: checkbox "Confirmar Reset" = False
   - Ejecutar reset
   - Verificar: retorna 400 con error

4. **`test_reset_por_tipo_contable`**
   - Ejecutar reset con tipo="contable"
   - Verificar: campos de Contable se resetean

5. **`test_reset_por_tipo_rrhh`**
   - Ejecutar reset con tipo="rrhh"
   - Verificar: campos de RRHH se resetean

6. **`test_reset_por_tipo_tickets`**
   - Ejecutar reset con tipo="tickets"
   - Verificar: campos de Tickets se resetean

---

### Cambio 5: Documentación

**Archivo nuevo:** `docs/dev/29-reset-mes-automatizado.md` (este archivo)

**Actualizar:** `docs/dev/28-cambio-de-mes-y-rotacion-manual.md` §15
- Documentar la idea nueva del usuario
- Referenciar este doc 29

---

### Cambio 6: Actualizar checklist maestro

**Archivo:** `docs/dev/11-checklist-maestro.md`

Agregar línea:
```
- [ ] 30. Reset automático de mes (endpoint + botón + checkbox)
```

---

## Implementación real (13-jul-2026) — ajustes respecto al plan

Al implementar contra el código real del backend surgieron 4 ajustes necesarios
(el plan de arriba se conserva como referencia histórica):

1. **El reset corre en un hilo de fondo (respuesta 202, no síncrona).**
   `render.yaml` arranca gunicorn **sin `--timeout`** (default 30s, 1 worker).
   Resetear ~330 filas = ~330 PATCHes ≈ 2 minutos: una request síncrona mataría
   el worker a los 30s y de paso bloquearía los webhooks F29 mientras tanto.
   El endpoint valida todo (secreto, tipo, checkbox), lanza `_reset_aplicar` en
   un `threading.Thread` daemon y responde `202 {"ok": true, "en_proceso": true,
   "filas_totales": N}`. El resultado final queda en el log
   (`reset-mes completado · filas_reseteadas=… · filas_fallidas=…`) y si alguna
   fila falla se avisa al admin vía `alertas.avisar_excepcion_admin`.

2. **`database_id` ≠ `data source id` (API 2025-09-03).** El botón manda el
   `database_id`, pero `query_data_source()` pega a `/data_sources/{id}/query`.
   Nuevo helper `nc.get_data_source_id(database_id)` que resuelve
   `GET /databases/{id}` → `data_sources[0].id` (con fallback al id tal cual si
   ya era un data source id). Los IDs de referencia están en doc 28 §16.

3. **Limpiar propiedades requiere payloads tipados, no `None` crudo.**
   Un `null` a nivel de propiedad es un 400 de la API de Notion. `RESET_CONTABLE`
   quedó con los payloads explícitos: `{"rich_text": []}`, `{"number": None}`,
   `{"date": None}`, `{"checkbox": False}`, `{"status": {"name": "sin empezar"}}`.

4. **La fila de control es OBLIGATORIA y se llama `RESET_MES`** (decisión del
   13-jul-2026: fila dedicada, separada de ZZ_TEST que sigue siendo la fila de
   pruebas de correo; el backend busca un título que CONTENGA "RESET_MES", así
   que "⚙️ RESET_MES" también vale). Más estricto que el pseudocódigo, que
   salteaba el check si no encontraba la fila: sin fila `RESET_MES` → 400; con
   fila pero checkbox desmarcado → 400. Además hay **guard de concurrencia**:
   un solo reset por base a la vez (segundo click → `{"duplicado": true}`).
   Notion no permite "fijar" filas en las vistas: para que quede siempre visible,
   ordenar las vistas para que aparezca arriba (el prefijo "⚙️" ayuda).

⚠️ **Verificar antes del E2E:** que el status se llame exactamente `sin empezar`
en Notion (¿o `Sin empezar`?). Si el nombre no coincide, la API rechaza el PATCH
de cada fila (se vería como `filas_fallidas=N` en el log + alerta al admin).

**Archivos tocados:** `notion_automation/app.py` (endpoint + `RESET_CONTABLE` +
`_reset_aplicar`/`_lanzar_reset`), `notion_automation/notion_client.py`
(`get_data_source_id`), `notion_automation/tests/test_reset_mes.py` (15 tests).

---

## Resumen de Archivos

| Archivo | Acción | Prioridad |
|---|---|---|
| `notion_automation/app.py` | Agregar endpoint `/reset-mes` | Alta |
| `notion_automation/tests/test_reset_mes.py` | Crear tests | Alta |
| `docs/dev/29-reset-mes-automatizado.md` | Crear documentación | Media |
| `docs/dev/28-cambio-de-mes-y-rotacion-manual.md` | Actualizar §15 | Media |
| `docs/dev/11-checklist-maestro.md` | Agregar tarea | Baja |

---

## Orden de Implementación

1. **Fase 1:** Endpoint `/reset-mes` para Contable (funcional)
2. **Fase 2:** Tests para Contable
3. **Fase 3:** Extender a RRHH y Tickets
4. **Fase 4:** Documentación
5. **Fase 5:** Actualizar docs existentes

---

## Notas para el LLM

- **No confundir `DS_CONTABLES`** con el reset. `DS_CONTABLES` es para el fallback por RUT (doc 28 §4.b). El reset usa `database_id` directamente.
- **El checkbox "Confirmar Reset" es OBLIGATORIO.** Sin él, el reset no se ejecuta. Esto previene resets accidentales.
- **Los campos estáticos NUNCA se tocan.** Solo se resetean los campos dinámicos listados arriba.
- **El botón se crea en la UI, no via API.** La API de Notion no permite crear botones configurados.
- **El backend es Flask.** Usa `request.get_json()` para leer el payload y `nc.update_props()` para escribir en Notion.
- **Tests usan mocks.** No se llama a la API real de Notion en tests unitarios.

---

**Anterior:** [`28-cambio-de-mes-y-rotacion-manual.md`](28-cambio-de-mes-y-rotacion-manual.md) ·
**Volver al** [`README`](README.md)
