# 33 · `ID Central` — la llave primaria compartida por las 5 tablas

> **Estado:** ✅ ejecutado y verificado (31-jul-2026)
> **Código:** [`notion_automation/id_central.py`](../../notion_automation/id_central.py) ·
> Fase 3 dentro de [`reconciliar.py`](../../notion_automation/reconciliar.py) `aplicar()`
> **Tests:** `notion_automation/tests/test_id_central.py` (18)

## 1 · El problema

El sandbox maestro `General Customers Data - AuditAI` tiene una columna `ID`
(`unique_id` de Notion) que es la **PK estable** de cada cliente: Notion la asigna, nunca
se repite ni cambia. Pero esa llave **solo vivía en la maestra**. Las 4 planillas donde
trabajan los asesores (Contable `<Mes>`, RRHH `<Mes>`, CRM Comercial, Tickets - Servicios)
no tenían ninguna llave común: unirlas exigía cruzar por RUT y, cuando no hay RUT (el CRM
tiene la columna vacía al 100%), por nombre y por parecido difuso. Eso sirve para
*descubrir* el enlace, pero no para *consultarlo*: no se puede hacer un `JOIN` de SQL
sobre un fuzzy match.

## 2 · La decisión

Copiar el número de la llave maestra a una columna **`ID Central`** (tipo *number*, mismo
nombre en las 4 planillas). Así `ID Central` (operativas) `==` `ID` (maestra) → las 5
tablas se unen por igualdad de llave, sin fuzzy.

- **Llave surrogate (interna):** `ID Central`. Garantiza el join incluso sin RUT.
- **Llave natural (negocio):** el `RUT` sigue siendo el identificador legal.
- No se puede crear una columna `unique_id` que "espeje" otra, por eso `ID Central` es
  *number* y guarda el valor.
- Las **relaciones** de Notion se mantienen: siguen alimentando los rollups vivos de la
  ficha. `ID Central` es el complemento para joins externos (SQL/métricas).

### Cambio de la regla de oro

La regla original decía *"las 4 planillas de los asesores NUNCA se escriben"*. El dueño
la **enmendó el 29-jul-2026**: ahora sí se pueden escribir, **únicamente** para integrar
`ID Central`. Ninguna otra columna, valor o dato de esas tablas se toca. Registrado en
[`AGENTS.md`](../../AGENTS.md) §Reglas de oro. Nota técnica: la integración ya tenía
permiso de escritura (el write-back de `Status`/`Fecha` de los botones), así que fue un
cambio de **política**, no de permisos.

## 3 · De dónde sale el mapeo (lo importante)

**No se re-cruza nada.** El cruce RUT → nombre → fuzzy ya lo hizo (y lo sigue haciendo
cada semana) [`reconciliar.py`](../../notion_automation/reconciliar.py), y su resultado
está guardado en las **relaciones ya pobladas** del sandbox (`Contable Origen`,
`RRHH Origen`, `CRM Origen`, `Tickets Origen`). Este módulo solo **propaga el ID** por
esas relaciones:

> para cada ficha maestra con `ID = N`, todas las filas operativas que cuelgan de sus
> relaciones reciben `ID Central = N`.

Consecuencias directas del diseño:

- Si un cliente tiene **varias filas** en una planilla (dos tickets), **todas** llevan el
  mismo `ID Central`: es el mismo cliente.
- Si una fila **no está ligada**, se queda **sin** `ID Central`. No se inventa: son los
  casos pendientes de revisión de Carlos.
- Si una fila cuelga de **dos fichas maestras distintas** (duplicado en la maestra), es un
  **conflicto**: tampoco se estampa, se reporta.

## 4 · Las 3 fases

| Fase | Qué hace | Cuándo |
|---|---|---|
| **1 · Esquema** | Crea la columna `ID Central` (number) donde falte. Idempotente. | Una vez (y automático al nacer la base RRHH del mes) |
| **2 · Backfill** | Estampa el ID en todas las filas ya ligadas. Idempotente. | Una vez (31-jul-2026) |
| **3 · Recurrente** | `reconciliar.aplicar()` estampa la llave en cada fila que liga, y en las filas que originan una ficha nueva (leyendo su `unique_id` recién asignado). | Cron semanal (lunes 09:00 UTC) |

La Fase 3 es la que mantiene el sistema vivo: cada semana las filas nuevas quedan
estampadas solas — sobre todo las de **RRHH**, que estrena base cada mes (`aplicar` crea
la columna en la base nueva antes de escribirla).

## 5 · Uso

```bash
python id_central.py                 # dry-run: esquema + plan de estampado (no escribe)
python id_central.py --esquema       # solo crea la columna donde falte
python id_central.py --aplicar       # crea columna + estampa (ESCRIBE)
python id_central.py --verificar     # cobertura y consistencia (solo lectura)
python id_central.py --fuente CRM    # acotar a una planilla
```

## 6 · Salvaguardas

1. **Solo `ID Central`.** Ninguna otra columna se crea, modifica ni borra en las planillas.
2. **Dry-run por defecto** y aprobación del dueño antes de escribir.
3. **Respaldo previo** a `backups/general-customers-data/<fecha>_pre-id-central.json`
   (page_id + valor previo; sin nombres ni RUT). Permite revertir el estampado.
4. **Idempotente:** escribe una fila solo si su valor difiere. Re-ejecutar no duplica nada.
5. **Sin PII en logs:** solo conteos, page_ids y el número del ID.
6. **Rate limit:** `request_con_reintentos` (backoff ante 429) + pausa de 0.34 s entre
   escrituras (~3 req/s, el límite de Notion). Nada en paralelo.
7. **Mes vigente:** Contable/RRHH se resuelven con `resolver_ds_actual`; nunca se
   hardcodea el mes. `candidatos_ds()` además cubre el caso de que la relación apunte a
   una base de un mes anterior: la fila se estampa donde de verdad vive.
8. **Columna ocupada:** si ya existiera un `ID Central` de otro tipo, se reporta como
   conflicto y **no se pisa**.

## 7 · Resultado verificado (31-jul-2026)

Columna creada en las 4 planillas y **507 filas estampadas**:

| Planilla | filas | con `ID Central` | clientes distintos |
|---|--:|--:|--:|
| Contable Julio | 295 | 288 | 287 |
| RRHH JUNIO 2026 | 54 | 45 | 45 |
| CRM Comercial | 135 | 106 | 106 |
| Tickets - Servicios | 89 | 68 | 67 |
| **Total** | **573** | **507** | **387 únicos** |

507 filas ≠ 507 clientes: son **387 clientes** contados una vez por planilla en la que
aparecen (287 están en 1 planilla, 82 en 2, 18 en 3) más 2 filas repetidas del mismo
cliente. De las 437 fichas de la maestra, 387 tienen contraparte operativa; 50 no.

**Consistencia (`--verificar`):** 0 discrepancias contra el `ID` de la ficha maestra y
**0 huérfanos** (ninguna fila con un ID que no exista en la maestra). Join de prueba en
SQL: Contable ∩ CRM = 51 clientes, Contable ∩ RRHH = 37, Contable ∩ Tickets = 30 — todos
unidos por igualdad de llave, sin un solo fuzzy.

**Sin estampar a propósito:** 66 filas operativas sin relación (los dudosos de Carlos) y
**7 filas de RRHH en conflicto** — cuelgan de una ficha antigua *y* de una duplicada
auto-creada el 27-jul (pares de ID 38/349, 45/348, 57/347, 101/350, 110/356, 146/351,
164/352). Se resuelven fusionando los duplicados de la maestra
(`reconciliar.py --duplicados`); el cron las estampa sola cuando queden con una sola ficha.

## 8 · Qué habilita

```sql
-- ficha 360º de un cliente, sin fuzzy
SELECT * FROM contable c
JOIN crm     m ON m.id_central = c.id_central
JOIN tickets t ON t.id_central = c.id_central
WHERE c.id_central = 128;
```

Métricas cruzadas (rentabilidad por cliente = honorario CRM vs. trabajo de Tickets/RRHH),
detección de inconsistencias entre planillas, y la base para la BD especializada del
[flujo de datos](07-flujo-de-datos.md).

## 9 · Relacionados

- [`24-arquitectura-multi-automatizacion.md`](24-arquitectura-multi-automatizacion.md) — las 4 planillas y sus esquemas.
- [`08-notion-general-customers-data.md`](08-notion-general-customers-data.md) — esquema de la maestra.
- [`09-seguridad-y-respaldo.md`](09-seguridad-y-respaldo.md) — protocolo de respaldo.
- [`28-cambio-de-mes-y-rotacion-manual.md`](28-cambio-de-mes-y-rotacion-manual.md) — rotación mensual de las bases.
