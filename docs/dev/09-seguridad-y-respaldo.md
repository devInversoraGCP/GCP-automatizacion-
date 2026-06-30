# 09 · Seguridad y respaldo de datos (protocolo obligatorio)

> **Para opencode y Claude.** Este es el procedimiento **obligatorio** antes de tocar la base de Notion "General Customers Data". Objetivo: **nunca dañar los datos originales** y poder **volver a una versión previa** si algo sale mal. Complementa la regla de acceso escalonado de [`../../AGENTS.md`](../../AGENTS.md) y el esquema de [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md).

## Reglas no negociables

1. **NUNCA trabajar sobre la tabla original.** Todo desarrollo y prueba de escritura se hace sobre una **copia (sandbox)**.
2. **Backup obligatorio antes de cualquier escritura** sobre el original (aunque sea autorizada).
3. **El historial y la papelera de Notion NO son un backup** (lo dice la propia Notion). El backup real son los **exports versionados fuera de Notion**.
4. Las credenciales (`CLAVE SII`, `Previred`) y PII (`RUT`, `email`, `Whatsapp`) **nunca** se imprimen ni se versionan en texto plano.

## Qué ofrece Notion (red secundaria, no suficiente)

| Mecanismo | Cubre | Retención |
|---|---|---|
| Historial de página (cada fila es página) | Revertir el **contenido** de una fila | Free 7d · Plus 30d · Business 90d · Enterprise ilimitado |
| Papelera (Trash) | Restaurar filas borradas | 30 días por defecto (Enterprise hasta 10 años) |

⚠️ No protege bien **cambios de esquema** (borrar/renombrar columnas) ni **cambios masivos**. Por eso usamos las 3 capas de abajo.

## Las 3 capas de seguridad (defensa en profundidad)

### Capa 1 — Copia sandbox (no tocar el original)
- Duplicar la base: en Notion, abrir "General Customers Data" → menú **`···`** (arriba a la derecha) → **Duplicate**. Renombrar la copia, p. ej. **"General Customers Data — SANDBOX"**.
- Desarrollar y probar **toda** la lógica de lectura/escritura contra la SANDBOX.
- El original solo se toca cuando algo está validado en la copia **y** existe backup fresco (Capa 2).
- ⚠️ Nota: las relaciones/rollups de la copia pueden seguir apuntando al original; para probar lógica de escritura suele dar igual, pero tenerlo presente.

### Capa 2 — Backup fuera de Notion = el verdadero control de versiones
- **Cuándo:** antes de cada sesión de trabajo y **siempre antes de cualquier escritura** sobre el original.
- **Cómo exportar:** abrir la base → menú **`···`** → **Export** → formato **Markdown & CSV** (el CSV es el respaldo de datos). Alternativa: Settings → Export all workspace content.
- **Dónde guardar:** carpeta `backups/general-customers-data/` con nombre **fechado**: `2026-06-30.csv`. Versionar esos snapshots da historial *diffeable* y restaurable.
- 🔴 **Seguridad del backup (importante):** el CSV trae credenciales y PII. **No** subirlo en texto plano a un repo compartido. Opciones:
  - guardar el export completo en un lugar **cifrado/privado** (fuera del repo), **o**
  - versionar en el repo solo una versión **redactada** (sin columnas `CLAVE SII`/`Previred`) y mantener la completa cifrada/offline.
  - Cuando el repo tenga git, añadir `backups/` (o los exports sensibles) a `.gitignore`.

### Capa 3 — Recuperación nativa de Notion (solo "ups" puntuales)
- **Revertir una fila:** abrir la página de la fila → `···` → **Page history** → elegir versión → **Restore**.
- **Restaurar fila borrada:** Papelera/Trash → restaurar (dentro de la retención).
- Sirve para errores de una fila; **no** para esquema ni masivos.

## Cuando se escribe en el original (prácticas obligatorias)

1. **Dry-run primero:** calcular y mostrar el *diff* (qué cambiaría) **sin aplicar**.
2. **Confirmación del usuario** por operación, mostrando **antes → después**.
3. **Apuntar por clave estable** (`userDefined:ID` o `RUT`), nunca por posición/orden.
4. **Prohibido** borrar en masa o modificar columnas/esquema por código sin OK explícito + backup fresco.
5. **Log de auditoría** de cada escritura: `id, columna, valor_anterior → valor_nuevo, timestamp`. Permite revertir a mano.
6. **Validar antes de escribir** (Pandera/Pydantic) — ver [`06-stack-tecnico.md`](06-stack-tecnico.md).

## Cómo restaurar si algo se dañó (orden de preferencia)
1. **Snapshot CSV** más reciente (Capa 2) → fuente de verdad para reconstruir.
2. **Page history** de la(s) fila(s) afectada(s) (Capa 3).
3. **Papelera** si se borró una fila.
4. Si el daño fue de esquema/masivo y no hay snapshot reciente → re-crear desde la **copia sandbox** o el último export bueno.

## Checklist antes de CUALQUIER escritura ✅
- [ ] ¿Existe backup CSV fechado de hoy, guardado de forma segura?
- [ ] ¿Estoy trabajando sobre la **SANDBOX**, no sobre el original?
- [ ] ¿Tengo el *diff* (dry-run) revisado y la confirmación del usuario?
- [ ] ¿Apunto por `ID`/`RUT` y no toco esquema ni hago borrados masivos?
- [ ] ¿Estoy registrando el cambio en el log de auditoría?

## Primeros pasos para arrancar con seguridad
1. **Confirmar el plan** del workspace de Notion (define la retención del historial).
2. Hacer el **primer export CSV** como *snapshot* base (guardado seguro).
3. Crear la **copia SANDBOX**.
4. Definir cadencia de backup y ubicación cifrada/privada de los respaldos sensibles.

---

**Anterior:** [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md) · **Volver al** [`README`](README.md)
