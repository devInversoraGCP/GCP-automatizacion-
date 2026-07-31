# 18 · Integración de `IMPUESTO ÚNICO` y `MONTO IMPOSICIONES|` a la base central

> **Brecha reportada por el usuario (02-jul-2026):** la base central `General Customers Data - AuditAI` no tenía las columnas `IMPUESTO ÚNICO` ni `MONTO IMPOSICIONES|`, que son **el insumo de la casilla 48 del F29** (retención de impuesto único a trabajadores — el único dato del cálculo que vive fuera del SII, ver [`17`](17-especificacion-literal-calculo-f29.md) §3.5). Este documento registra el diseño, los hallazgos y la ejecución de la integración.

## 1 · Dónde viven los datos (hallazgos, 02-jul-2026)

Las dos columnas existen **solo** en las bases mensuales de RR.HH. (no en `Contable Mayo`, que solo tiene una columna genérica `Impuestos`):

| Base | Data source | Filas | Con `IMPUESTO ÚNICO` | Con `MONTO IMPOSICIONES\|` | Con RUT en título |
|---|---|---|---|---|---|
| `RRHH MAYO 2026` | `36612147-b3ea-81f6-89b8-000b1f03c1c5` | 52 | 23 | 34 | 21 |
| `RRHH JUNIO 2026` | `9c512147-b3ea-8256-a570-871254c13b3d` | 51 | 9 | 14 | 21 |

- **No existen** bases RRHH de meses anteriores (abril, marzo…) — solo MAYO y JUNIO.
- El universo real de clientes con RR.HH. es **~52 de los 331** (consistente con que 301 no tienen `Adviser RR.HH`). Los demás clientes **no tienen trabajadores gestionados por GCP** → su casilla 48 = 0.
- JUNIO está **en llenado activo** por el equipo GCP (por eso 9/51); los valores crecerán durante el ciclo mensual.
- ⚠️ Ambos son **valores mensuales**, no atributos fijos del cliente (ver §4).

## 2 · Diseño: relación + rollup (patrón D19)

Igual que con `USUARIO-Previred`/`CLAVE-Previred`: los valores **no pasan por el agente**, fluyen por la relación existente `RRHH Origen` (sandbox → `RRHH JUNIO 2026`).

Ejecutado el 02-jul-2026 en la sandbox (`4ff12147-b3ea-82f4-98dd-072067524cdc`):

1. **2 columnas rollup nuevas** (la base pasa de 28 a **30 columnas**):
   - `IMPUESTO ÚNICO` = rollup(`RRHH Origen` → `IMPUESTO ÚNICO`, show_original)
   - `MONTO IMPOSICIONES|` = rollup(`RRHH Origen` → `MONTO IMPOSICIONES|`, show_original)
2. **Poblado de la relación `RRHH Origen`**: estaba poblada solo en 18 filas; se ligaron **+18 matches seguros** (RUT idéntico o nombre inequívoco) → **36 filas ligadas**. Dry-run y log: `backups/general-customers-data/2026-07-02_dry-run-rrhh-origen-junio.json`.

## 3 · Estado del match RRHH JUNIO (53 filas al 06-jul) ↔ sandbox

| Categoría | Nº | Acción |
|---|---|---|
| Ya ligadas (pre-existentes) | 18 | — (1 de ellas tenía **enlace muerto**, corregido 06-jul, ver nota) |
| **Matches seguros → ligados 02-jul** | **18** | ✅ ejecutado |
| **Probables → confirmados por el usuario y ligados 05-jul** | **6** | ✅ ejecutado |
| **TEACREDITO RENT → confirmado por el usuario y ligado 06-jul** | **1** | ✅ ejecutado (antes listado como "sin ficha") |
| Ambiguos (2 candidatos en la base) | 3 | 🧑‍💼 escalado a Carlos (pregunta #8 de [`05`](05-decisiones-y-preguntas.md)) |
| Sin ficha en la base central | 5 | 🧑‍💼 escalado a Carlos (pregunta #8 de [`05`](05-decisiones-y-preguntas.md)) |
| Duplicado (ESR, 2ª fila) / fila basura | 2 | no ligar / limpiar en origen (con permiso) |
| Filas nuevas / por identificar (detectadas 06-jul) | ~1 | 🔎 identificar (la planilla creció; ver nota) |

**Total ligadas: 42/53** (verificación 06-jul: la sandbox tiene 42 filas con `RRHH Origen` y **los 42 enlaces apuntan a filas existentes de JUNIO**, cruce URL a URL). Probables confirmados el 05-jul ("asi es", usuario): LA PORTERIA→Porteria.com · PROCLEAN-VICUÑA 2→PROCLEAN (EMPRESA VICUÑA) · LAB4D→LAB4 SPA · CIES→Centro Integral de Educación y Salud · Seba Reyes→SEBASTIAN REYES CELIS · NEUROCIRUGIA-Empresarial→Neurocirugia Chile Spa.

> 🔧 **Corrección 06-jul (TEACREDITO RENT):** el usuario confirmó que la fila `TEACREDITO RENT` de JUNIO **es el mismo registro** que el cliente `Teacredito rent` de la sandbox. Al aplicarlo se descubrió que esa ficha tenía un **enlace muerto** en `RRHH Origen` (apuntaba a una página que no existe en JUNIO ni en MAYO — contado erróneamente entre las 18 "pre-existentes"); se re-apuntó a la fila real de JUNIO. Log: `backups/general-customers-data/2026-07-06_link-rrhh-origen-teacredito.md`.
>
> 📌 **Nota 06-jul:** JUNIO tiene hoy **53 filas** (el conteo anterior decía 51; la planilla está en llenado activo). Quedan **11 sin ligar** = 3 ambiguos + 5 sin ficha + 2 dup/basura + ~1 fila por identificar.

**Ambiguos (para Carlos):** ABURTO KRAMP (¿Aburto Kramp o Consultora Aburto KRAMP?) · MARISIO JEREZ Y CIA (¿= MARISIO JEREZ INVERSIONES LTDA?) · OLIVERO PARTENS (¿INVESTMENT o SPA?).
**Sin ficha en GCD (para Carlos, ¿se crean?):** Hector Hugo Valenzuela-ASESORA · SERVICIOS INTEGRALES MJ · CONST. UMBRAL · BLUELETRIC · AGUIRRE SPA (⚠️ tiene ambos valores).
~~TEACREDITO RENT~~ → resuelto y ligado el 06-jul (ver corrección arriba).

> Regla vigente: **jamás** asociar por similitud difusa (lección Zsabesky); lo no-inequívoco se escala al usuario/cliente.

## 4 · Nota de diseño: son datos MENSUALES

`IMPUESTO ÚNICO`/`MONTO IMPOSICIONES|` cambian todos los meses. Decisiones que esto implica:

- La relación `RRHH Origen` apunta al mes que se declara ahora — el rollup siempre muestra "el mes vigente". ✅ **AUTOMATIZADO (31-jul-2026):** `reconciliar.sincronizar_relacion()` compara la relación con la base del mes vigente en cada corrida del cron y la re-apunta sola. Ya no es un paso manual. Detalle y hallazgos en [`33`](33-id-central-llave-compartida.md) §10.
    - ⚠️ Dos comportamientos de la API de Notion verificados el 31-jul, que hacían de esto una bomba silenciosa: (1) re-apuntar una relación **borra** sus enlaces; (2) escribir un enlace a una fila de **otro** data source devuelve 200 pero **no guarda nada** — el cron creía ligar 47 filas y no ligaba ninguna, sin error.
    - Desde que existe `ID Central`, borrar los enlaces ya **no pierde trazabilidad**: la llave queda escrita en la propia fila del mes viejo (verificado: las 45 filas de RRHH JUNIO conservan su `ID Central`).
- El **motor de cálculo** (Frente B) no dependerá del rollup: leerá directamente `RRHH <Mes>` del período que calcula.
- **No se mezclan meses**: los datos de MAYO no se copian a los rollups de JUNIO; si falta el valor de junio de un cliente, se espera a que GCP lo llene o se pregunta.

## 5 · Pendientes

- [x] ~~Resolver con el usuario los 6 probables~~ → confirmados y ligados (05-jul).
- [x] ~~TEACREDITO RENT~~ → confirmado por el usuario como el mismo registro que `Teacredito rent` y ligado (06-jul).
- [ ] 🧑‍💼 Resolver con **Carlos** los 3 ambiguos + 5 sin ficha (pregunta #8 de [`05`](05-decisiones-y-preguntas.md)).
- [ ] 🔎 Identificar las filas nuevas de JUNIO (la planilla pasó de 51 a **53 filas**; ~1 sin categoría conocida).
- [ ] Definir el mecanismo de "cambio de mes" de la relación (manual asistido vs automático).
- [ ] Actualizar el conteo de completitud en [`08`](08-notion-general-customers-data.md) tras resolver pendientes.
- [x] Verificación numérica final: **42/331 filas con `RRHH Origen`** confirmadas por query SQL (05-jul). Re-verificado el **06-jul**: 42/331, y los 42 enlaces apuntan a filas existentes de JUNIO (se corrigió 1 enlace muerto).

---

**Anterior:** [`17-especificacion-literal-calculo-f29.md`](17-especificacion-literal-calculo-f29.md) · **Volver al** [`README`](README.md)
