# 15 · Barrido de bases contables mensuales — plan de acción y guía para un LLM

> **Documento de trabajo ejecutable.** Registra el descubrimiento de las **bases contables mensuales** de Notion (más allá de "Contable Mayo") y detalla, paso a paso, cómo un LLM debe (A) **rescatar los 4 RUTs faltantes** de la sandbox y (B) **enriquecer toda la base** con estas fuentes nuevas.
>
> **Estado:** 🟡 en ejecución — barrido de Febrero completo (02-jul-2026 tarde): **1/7 claves rescatada y escrita** (Escuela de Voces Manuela), **6/7 + RUT de Steven no aparecen en ninguna base mensual → escalados al usuario**. Solo existen 2 meses en el workspace (Mayo + Febrero). Creado el **02-jul-2026**.
>
> 🔒 = toca credenciales/PII · 🧮 = lógica determinista. **Este documento vive en el repo (`docs/dev/`), que SÍ se versiona en git → NUNCA escribir aquí valores reales de `RUT`, `CLAVE SII`, `email`, `Previred`, `USUARIO`/`CLAVE` ni ningún PII.** Solo nombres (title), IDs internos y URLs de página.

---

## 0 · Cómo usar este documento (si eres un LLM que retoma el trabajo)

**Lee primero, en este orden:**
1. [`../../AGENTS.md`](../../AGENTS.md) — reglas de oro no negociables (seguridad, PII, sandbox).
2. [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md) — decisiones D1–D23 (en especial **D21** precedencia de fuentes y **D15/D17** seguridad y PII).
3. [`13-fase-c-volcado-nuevos-registros.md`](13-fase-c-volcado-nuevos-registros.md) y [`14-construccion-dataset-y-anomalias.md`](14-construccion-dataset-y-anomalias.md) — cómo se construyó la base (334 tras Fase C; **331 actual** tras cierre del Frente A) y las decisiones (ya resueltas).
4. **Este documento** para el barrido.

**Autorización vigente:** el usuario dio **plena libertad de lectura/escritura sobre la sandbox** `General Customers Data - AuditAI` (ver [`../../AGENTS.md`](../../AGENTS.md)). El **original** y demás bases del cliente son **solo lectura**. Las bases contables mensuales se leen; **jamás se escriben**.

**Regla de oro operativa:** todo lo que se escriba va a la **sandbox**, con **backup fresco + dry-run + log de auditoría**. Nunca se imprime un RUT/clave/email en el chat ni en este repo.

---

## 1 · Contexto y por qué existe este barrido

Durante la Fase 1 se usó **una sola** base auxiliar contable: **"Contable Mayo"**. El 02-jul-2026, buscando el RUT de un cliente sin identificar (**XIT**), se descubrió que existe una **familia de bases contables mensuales** (p. ej. **"Contable Febrero"**), cada una con su **propio roster de clientes**, con `Rut`, `Clave SII`, `Email`, `Adviser Accounting` y `CRM`. Es decir, **"Contable Mayo" no era la única fuente**: hay más meses con datos que no se incorporaron.

**Consecuencia:** el veredicto anterior de "cliente sin candidato / RUT no recuperable" era **prematuro**. XIT se resolvió en minutos leyendo "Contable Febrero". Faltan 4 por buscar en el resto de los meses, y probablemente estas bases puedan **completar huecos en toda la base** (claves, emails, RUTs de otros clientes).

---

## 2 · Objetivo

> 🎯 **Objetivo principal (definido 02-jul-2026): llegar al 100% de registros "listos para automatización SII"** (`RUT` válido + `CLAVE SII`). Hoy la base tiene **330 con RUT válido** pero solo **323 con Clave SII** → hay **7 registros que tienen RUT pero NO Clave SII**. Recuperar esas 7 claves desde las bases contables mensuales es la meta central de este barrido.

**A · Recuperar la `CLAVE SII` de los 7 registros con RUT pero sin clave** (lista en §3). Con eso, los "listos para SII" pasan de 323 → **330 (≈100% de los que tienen RUT)**.
> 🔁 **Regla de escalamiento (decisión del usuario):** si tras barrer **todas** las bases mensuales una clave **no aparece en ninguna parte de Notion**, se **documenta con evidencia** y se **escala al usuario** para que pregunte a su cliente qué hacer con ese registro. No se inventa ni se adivina una clave, jamás.

**B · Rescatar el `RUT` de `Steven`** (ID 48), el único cliente que quedó sin RUT tras el cierre del Frente A (los otros 3 sin RUT fueron descartados; XIT ya se resolvió).
**C · Enriquecer toda la base** con las fuentes mensuales: completar `RUT`, `CLAVE SII`, `email`, `Adviser Accounting`, `CRM` donde falten, aplicando la precedencia D21.

**Criterio de éxito:**
- Los 7 registros tienen `CLAVE SII` (→ 100% de los con RUT quedan listos para SII), **o** se documenta con evidencia que la clave no existe en ninguna base mensual → escalar al usuario/cliente.
- `Steven` tiene RUT (o se documenta que no existe).
- Re-medición de completitud de la base; todo trazado en el log de auditoría; cero PII expuesto.

---

## 3 · Estado actual (checklist de progreso — mantener vivo)

### Objetivo A — 7 registros con RUT pero SIN Clave SII (meta principal 🎯)

Detectados en vivo el 02-jul-2026 (`RUT` poblado + `CLAVE SII` vacía). Buscar su clave en las bases mensuales por **RUT** (clave de cruce fuerte) y por nombre:

| # | Cliente | ID sandbox | Origen | Nota |
|---|---|---|---|---|
| 1 | **INVERSORA GCP** | 333 | RRHH Junio 2026 | Vino de RRHH (que no trae Clave SII). Buscar en meses contables. |
| 2 | **JAVIERA COMPAN** | 334 | RRHH Junio 2026 | Ídem. Es adviser/persona; verificar si es cliente facturable. |
| 3 | **Servicios Oporto** | 179 | Contable Mayo | En Contable Mayo su `Clave SII` estaba vacía; puede estar en otro mes. |
| 4 | **Kahi** | 102 | Original | Original sin clave. |
| 5 | **Escuela de Voces Manuela** | 80 | Original | Original sin clave. |
| 6 | **IMAGINE MATTERS SPA** | 30 | Original | Original sin clave. |
| 7 | **Vitalia Ventures SpA** | 86 | Original | Original sin clave. |

> 🔁 **Regla de escalamiento:** si la clave de alguno **no aparece en ninguna base mensual**, se documenta y se **pregunta al cliente** (no se inventa).

### Objetivo B — Steven, único cliente sin RUT

| Cliente | ID sandbox | Página Notion | Pistas de contexto | Estado |
|---|---|---|---|---|
| **Steven** | 48 | `e2412147b3ea83338e2f01a07f484d8e` | Adviser **Carlos Cereceda** · etiqueta **"27 bis"** (Art. 27 bis IVA) | ⏳ pendiente |

> 💡 **Pista:** Steven es cliente de **Carlos Cereceda**, grupo **"27 bis"**. Buscar en los meses filas de Carlos / del grupo 27 bis cuyo nombre empiece por "Steven" (posiblemente con apellido/empresa completos), o preguntar a Carlos.

> **Contexto histórico (02-jul-2026):** eran 5 clientes sin RUT. **XIT** se resolvió (RUT de Contable Febrero). **Sergio ??** (78), **Patricia** (50) y **Zsabesky Servicios** (113) fueron **descartados** por el cliente y **movidos** a la página `🗑️ Descartados AuditAI` (`39112147-b3ea-812e-822b-ff1afac2c9eb`). Queda solo **Steven**. La hipótesis "Zsabesky ≈ Szabelewski" fue **descartada** por el usuario.

### Barrido de fuentes

> **Resultado del barrido (02-jul-2026, tarde):** se enumeró todo el workspace con `notion-search "Contable"`. **Solo existen 2 meses**: Mayo (ya incorporada) y Febrero (3 data sources: `e4c12147` principal 224 filas, `9ad12147` **vacía**, `ff412147` duplicada 224 filas idénticas). **No hay Enero/Marzo/Abril/Junio/Julio ni ningún otro mes.** Se barrió Febrero completo (principal + copia duplicada; la copia vacía no aporta) cruzando los 7 RUTs objetivo por RUT (llave fuerte) + Steven por nombre y por contexto (Carlos Cereceda / grupo "27 bis").

- [x] "Contable Mayo" (data source `fdb12147-…`) — ya incorporada en Fase A/B/C. Fuente **única** (la database `37212147` no es multi-source).
- [x] "Contable Febrero" (data source `e4c12147-…`) — **barrido completo por RUT** (3 páginas, 224 filas). Resultado: solo `Escuela de Voces Manuela` (RUT `77621486-8`) aparece, con `Clave SII` poblada. Los otros 6 RUTs objetivo **no existen** en esta base. `STIVEN CARTAGENA EIRL` (`76770671-5`) aparece pero es **otro cliente (ID 140)**, no Steven.
- [x] "Contable Febrero (1)" — copia `9ad12147` (parent `3cc12147`): **vacía** (0 filas). Copia `ff412147` (parent `34e12147`): 224 filas **idénticas** a la principal (mismos RUTs/claves; Escuela reaparece). No aportan nada nuevo.
- [x] **Enumeración de meses:** completa. **No hay más meses** además de Mayo y Febrero.
- [x] **Objetivo A — 7 claves SII:** ✅ **1/7 rescatada y escrita** (Escuela de Voces Manuela, ID 80 → `CLAVE SII` copiada desde Febrero, escrita en sandbox page `6da12147`, log en `log-auditoria-volcado.csv`). ❌ **6/7 no aparecen en ninguna base mensual** → **escalamiento al usuario** (ver §14 abajo).
- [x] **Objetivo B — Steven:** ❌ **no aparece en ninguna base mensual** (ni por nombre "Steven", ni en la intersección Carlos+27bis que dio 10 filas ninguna llamada Steven). `STIVEN CARTAGENA` descartado (es ID 140). → **escalamiento al usuario** (consulta a Carlos Cereceda).
- [ ] **Objetivo C —** enriquecimiento general de la base con todos los meses. *(Dado que solo Febrero es nueva y los 6 RUTs objetivo no están, el enriquecimiento se limitaría a emails/advisers/CRM de Febrero para los registros ya presentes — trabajo secundario, pendiente de priorización.)*

### ⏫ Escalamiento al usuario (02-jul-2026, tarde)

Per la regla de escalamiento (§2): si una clave no aparece en ninguna base mensual de Notion, se documenta con evidencia y se escala — nunca se inventa. **Evidencia del barrido:**

| # | Cliente | ID sandbox | Adviser | RUT (en sandbox) | ¿Aparece en Febrero? | Acción requerida |
|---|---|---|---|---|---|---|
| 1 | INVERSORA GCP | 333 | Carlos Cereceda | (RUT válido) | ❌ no | preguntar al cliente la Clave SII |
| 2 | JAVIERA COMPAN | 334 | — (es adviser/persona) | (RUT válido) | ❌ no | preguntar al cliente la Clave SII |
| 3 | Servicios Oporto | 179 | Carlos Cereceda | (RUT válido) | ❌ no | preguntar a Carlos Cereceda |
| 4 | Kahi | 102 | Sebastián Robles | (RUT válido) | ❌ no | preguntar a Sebastián Robles |
| 5 | ~~Escuela de Voces Manuela~~ | ~~80~~ | ~~Carlos Cereceda~~ | ~~(RUT válido)~~ | ✅ **SÍ (resuelta)** | ~~hecho~~ |
| 6 | IMAGINE MATTERS SPA | 30 | ANDREA GONZALEZ | (RUT válido) | ❌ no | preguntar al cliente la Clave SII |
| 7 | Vitalia Ventures SpA | 86 | Carlos Cereceda | (RUT válido) | ❌ no | preguntar a Carlos Cereceda |
| — | **Steven** | 48 | Carlos Cereceda | **(sin RUT)** | ❌ no | preguntar a Carlos Cereceda el RUT (y la Clave SII) |

> **Conclusión del barrido:** con la única base nueva disponible (Febrero) ya barrida, **no es posible recuperar las 6 claves restantes ni el RUT de Steven desde Notion**. El gate del Frente A (D18) queda bloqueado por estos 7 casos hasta que el usuario consiga los datos con su cliente (principalmente **Carlos Cereceda**, adviser de 4 de los 7). Tras la escritura de Escuela, los "listos para SII" pasan de **323 → 324** (de 330 con RUT).

### 🔍 Pendientes para revisión manual con Carlos Cereceda (enriquecimiento Febrero)

Durante el enriquecimiento general (Objetivo C, cruce sandbox↔Febrero por RUT, 217 matches) surgieron **8 consultas que el usuario decidió dejar pendientes para revisarlas con Carlos Cereceda**. No se escribieron automáticamente; quedan aquí para que Carlos las resuelva caso a caso. Detalle completo (sin PII) en `backups/general-customers-data/2026-07-02_dry-run-enriquecimiento-febrero-publico.csv`.

**A) "Sandra Jerez Boss" como gestor CRM (7 casos):** el CRM multi_select de estos 7 clientes trae `Sandra Jerez, Giovanni Marisio` (o solo `Sandra Jerez`), y Febrero aporta una etiqueta nueva `Sandra Jerez Boss`. **Pregunta para Carlos:** ¿`Sandra Jerez Boss` es un gestor/rol **distinto** legítimo que debe añadirse al CRM de estos clientes, o es una **variante/duplicado** de `Sandra Jerez` que no debe añadirse?

| ID | Cliente | CRM actual (sandbox) | Febrero aporta | Acción si Carlos confirma |
|---|---|---|---|---|
| 171 | Sandra Jerez | Sandra Jerez, Giovanni Marisio | Sandra Jerez Boss | añadir / descartar |
| 126 | Dahia Jerez | Sandra Jerez, Giovanni Marisio | Sandra Jerez Boss | añadir / descartar |
| 170 | Giovanni Marisio | Sandra Jerez, Giovanni Marisio | Sandra Jerez Boss | añadir / descartar |
| 76 | Teacredito rent | Sandra Jerez, Giovanni Marisio | Sandra Jerez Boss | añadir / descartar |
| 75 | MARISIO JEREZ INVERSIONES LTDA | Sandra Jerez, Giovanni Marisio | Sandra Jerez Boss | añadir / descartar |
| 109 | JCRent SpA - Renta Car | Sandra Jerez | Sandra Jerez Boss | añadir / descartar |
| 98 | Sozial SpA | Sandra Jerez, Giovanni Marisio | Sandra Jerez Boss | añadir / descartar |

**B) KYRA SpA (ID 145) — gestor con apellido distinto entre bases:** el CRM en Mayo (sandbox) dice `Benjamin Subiare`; Febrero dice `Benjamin Kusuvak`. **Pregunta para Carlos:** ¿cuál es el gestor correcto de KYRA SpA — `Benjamin Subiare` (Mayo, mantener) o `Benjamin Kusuvak` (Febrero, sobrescribir)? Probablemente un error de tipeo en alguna de las dos bases.

> Estado de estas 8: ⏳ **pendiente de consulta a Carlos Cereceda**. No se aplicó ninguna escritura sobre estos casos. Cuando Carlos responda, aplicar las confirmadas con backup + log de auditoría.

### ❌ Escrituras descartadas del enriquecimiento Febrero (decisión del usuario, 02-jul-2026)

El usuario revisó las 4 escrituras restantes del dry-run y decidió **descartarlas** (no escribir) con estos motivos:

| # | ID | Cliente | Campo | Motivo del descarte |
|---|---|---|---|---|
| 1 | 165 | XIT | Adviser Accounting (LLENAR) | El `user_id` de Febrero (`ee9ea4c9…`) **no es un asesor real** (no resuelve a persona identificada). Se omite — mejor dejar XIT sin adviser. |
| 2 | 251 | Sweet Dent | CRM (merge "Dulce Rivero") | Es la **misma persona** que "Dulce rivero" ya en sandbox (solo difiere en mayúsculas). No se discrimina por capitalización → no añadir. |
| 3 | 123 | Open | CRM (merge "Paulina") | Es la **misma persona** que "Paulina Diaz" ya en sandbox (versión sin apellido). No añadir. |
| 4 | 122 | FJKFIT SpA | CRM (merge "Felipe kosovack") | Es la **misma persona** que "Felipe Kosovac" ya en sandbox (typo de tipeo). No añadir. |

> **Resultado final del enriquecimiento (Objetivo C):** 0 escrituras aplicadas del cruce Febrero. La única escritura del barrido fue la **CLAVE SII de Escuela de Voces Manuela** (Objetivo A). Los 88 SOBRESCRIBRIR de adviser se descartaron (Mayo más reciente predomina), las 8 ambiguas quedan para Carlos, y estas 4 se descartaron por ser la misma persona o un asesor no real. Febrero no aporta datos nuevos útiles más allá de la clave ya rescatada.

> **Nota de sesión (02-jul-2026):** barrido **completo** (solo existen Mayo + Febrero en el workspace; Febrero barrido en su totalidad). El gate del Frente A queda bloqueado por 7 casos (6 claves SII + RUT de Steven) que requieren consulta al cliente — ver tabla de escalamiento arriba y las 8 consultas pendientes para Carlos Cereceda.

---

## 4 · Las bases contables mensuales (enumeración COMPLETA — 02-jul-2026)

> **Resultado de la enumeración (`notion-search "Contable"`):** en el workspace **solo existen 2 meses**: **Mayo** y **Febrero**. **No hay Enero, Marzo, Abril, Junio, Julio ni ningún otro.** Febrero aparece triplicado (1 data source principal con datos + 1 vacío + 1 duplicado idéntico). Todas comparten el mismo esquema que "Contable Mayo", bajo `Inversora GCP SpA → CONTABILIDAD - SII - TESORERÍA`.

**IDs confirmados (verificados en vivo):**

| Base / mes | database ID | data source | Filas | Notas |
|---|---|---|---|---|
| Contable Mayo | `37212147-b3ea-80fa-ab06-cfd9782372a9` | `fdb12147-b3ea-820b-8595-07535e078336` | 283 | Ya incorporada en Fase A/B/C. Fuente única (no multi-source). |
| Contable Febrero *(principal)* | `3ae12147-b3ea-839d-b941-81946a083c62` | `e4c12147-b3ea-83f4-a4eb-07dabe205145` | 224 | XIT vive aquí. **Barrido completo (02-jul):** 1/7 rescatado (Escuela de Voces Manuela). |
| Contable Febrero (1) *(dup)* | `3cc12147-b3ea-824a-9aee-81b085a57917` | `9ad12147-b3ea-82f5-bcbc-073d83f34aa7` | **0** | **Vacía** (copia sin datos). |
| Contable Febrero (1) *(dup)* | `34e12147-b3ea-82f6-bdbc-01f5814f339b` | `ff412147-b3ea-8246-b319-872445a8fe0a` | 224 | **Duplicada idéntica** del principal (mismos RUTs/claves; no aporta nada nuevo). |
| ~~Contable Enero / Marzo / Abril / …~~ | — | — | — | **No existen** en el workspace. |

> **Nota de anidación:** los 3 data sources de Febrero están anidados — el principal (`3ae12147`) y `3cc12147` viven bajo Mayo (`37212147`); `34e12147` vive bajo `3cc12147`. La estructura completa es: `Mayo → {Febrero principal, db 3cc12147 → db 34e12147}`.

**Cómo enumerar el resto (Tarea 1):**
- `notion-search` con `query:"Contable"`, `query_type:"internal"`, `page_size:20` → lista databases "Contable <Mes>".
- Para cada database encontrada, `notion-fetch` con su ID → leer el/los `<data-source url="collection://…">` de su esquema.
- También `notion-fetch` de la base `37212147-…` por si es **multi-source** (varias data sources = varios meses bajo un mismo database).
- Registrar aquí la tabla completa de meses → data source IDs antes de barrer.

**Esquema de cada base contable (columnas útiles):** `Customers` (title = nombre), `Rut`, `Clave SII` 🔒, `Email` 🔒, `Adviser Accounting` (person, ya trae user IDs de Notion), `CRM` (select), + operativas que no se usan (`Status`, `ARec`, `Fecha`, `Month`, checkboxes, etc.).

---

## 5 · Mapeo de campos (fuente mensual → sandbox)

| Campo fuente (Contable <Mes>) | Campo sandbox (GCD - AuditAI) | Notas |
|---|---|---|
| `Customers` (title) | `w` / llave de cruce | Normalizar para el match (ver §7). |
| `Rut` | `RUT` | Normalizar + validar DV módulo 11 (ver §8). |
| `Clave SII` 🔒 | `CLAVE SII` | Copiar tal cual si presente. Nunca imprimir. |
| `Email` 🔒 | `email` | Validar formato; si trae varios/notas → cola de limpieza (ver [`14`](14-construccion-dataset-y-anomalias.md) §4.3). |
| `Adviser Accounting` (person) | `Adviser Accounting` | Ya viene como `["user://<id>"]`; escribir igual. |
| `CRM` (select) | `CRM` | Copiar opciones existentes. |

Campos sandbox **sin fuente** en estas bases: `Whatsapp`, `RUT RL`, `Rubro`, `Segmentación`, `Ciudad`, `Municipalidad`, `Previred`/`USUARIO-Previred`/`CLAVE-Previred` (esos vienen de RRHH), `Drive Empresa`, etc.

---

## 6 · Algoritmo del barrido 🧮

```text
# A-BARRIDO · Consolidar meses + rescatar 4 + enriquecer base

ENTRADAS:
  sandbox     ← query completa de GCD-AuditAI (334 filas)  [collection://4ff12147-...]
  meses[]     ← lista de data sources "Contable <Mes>" (Tarea 1)
  objetivos4  ← {Sergio ?? (78), Patricia (50), Steven (48), Zsabesky Servicios (113)}

# ── PASO 1 · Consolidar todos los meses en un índice local ──────────
consolidado ← {}                       # clave: RUT_normalizado_valido
para cada ds en meses:
    filas ← query paginada SELECT "Customers","Rut","Clave SII","Email",
                                   "Adviser Accounting","CRM" FROM ds   # LIMIT 100 OFFSET…
    guardar filas crudas en scratchpad (JSON)   # NO en el repo (traen credenciales)
    para cada fila:
        rn ← normalizar_y_validar_rut(fila.Rut)      # §8
        si rn válido:
            # precedencia: el mes MÁS RECIENTE gana para campos que cambian (clave/email);
            # para RUT da igual (no cambia). Registrar mes de origen.
            fusionar_en(consolidado[rn], fila, mes=ds.mes)

# ── PASO 2 · Rescatar los 4 RUTs faltantes ──────────────────────────
para cada obj en objetivos4:
    candidatos ← buscar en consolidado por:
        1) nombre normalizado exacto (norm(Customers) == norm(obj.w))
        2) nombre que EMPIECE por el nombre de pila (para Sergio/Patricia/Steven)
        3) para el grupo "27 bis": filtrar filas cuyo Adviser == Carlos Cereceda
           (user 4248c8ac-2436-4216-b602-ba3e727f631e) y revisar manual
    si 1 candidato claro: proponer RUT (+clave/email/adviser/crm) para ese obj
    si varios/ninguno:    marcar para revisión humana (no adivinar)

# ── PASO 3 · Enriquecimiento general (toda la base) ─────────────────
para cada cliente C en sandbox con RUT válido:
    m ← consolidado[C.RUT_normalizado]
    si m existe:
        para campo en [CLAVE SII, email, Adviser Accounting, CRM, RUT]:
            si C[campo] vacío y m[campo] presente:            → proponer (LLENAR)
            si C[campo] presente y m[campo] ≠ C[campo]:        → proponer (SOBRESCRIBIR, D21)
                                                                  (excepto email inválido → cola)

# ── PASO 4 · Dry-run → confirmación → escritura ─────────────────────
generar diff completo (público sin PII en backups/, privado con valores en backups/)
mostrar RESUMEN por campo al usuario (conteos, SIN PII)
esperar luz verde
escribir en sandbox por página (update_properties), throttling ≤ 3 req/s
log de auditoría por cada escritura (sin valores de clave/PII)

# ── PASO 5 · Verificación ───────────────────────────────────────────
re-medir completitud (§ métricas de doc 14)
actualizar §3 de este documento + doc 14 + checklist 11
```

---

## 7 · Normalización de nombre (para el match) 🧮

```text
norm(s) = trim → minúsculas → sin tildes → colapsar espacios
          → quitar sufijos societarios (SPA, S.A, LTDA, EIRL, LIMITADA)
Para Sergio/Patricia/Steven: comparar por PREFIJO (startswith nombre de pila),
porque en la sandbox están con nombre incompleto (p. ej. "Sergio ??").
Todo match dudoso → cola de revisión humana. NUNCA escribir sobre un match incierto.
```

---

## 8 · Validación de RUT (dígito verificador módulo 11) 🧮

```text
normalizar: quitar puntos y espacios, mayúscula la K, separar cuerpo y DV.
s = 2; suma = 0
para cada dígito d de cuerpo, de derecha a izquierda:
    suma += d * s
    s = 2 si s == 7 sino s + 1        # ciclo correcto 2,3,4,5,6,7,2,3,…
resto = 11 - (suma mod 11)
DV = "0" si resto==11 ; "K" si resto==10 ; str(resto) en otro caso
válido ⟺ DV_calculado == DV_dado
```
> 🐛 Ojo: el ciclo vuelve a **2** tras el 7 (no a 3). Ver corrección documentada en [`12`](12-fase1-plan-detallado.md) §A2.1.

---

## 9 · Mapa de usuarios (advisers) — para leer/escribir campos `person`

| user id (Notion) | Nombre |
|---|---|
| `fe346428-59fa-4cb0-9fab-ff30feefcc92` | ANDREA GONZALEZ |
| `4248c8ac-2436-4216-b602-ba3e727f631e` | Carlos Cereceda |
| `33bd872b-594c-8163-87bc-00026e7cbeb6` | Constanza Gaggero |
| `2a3d872b-594c-811d-b714-00024ff6e675` | Matilde Mateluna |
| `91e6795d-f1aa-40b0-a748-4c3b88fb3f82` | Sebastián Robles |
| `ee9ea4c9-fc0b-48be-af68-2cb0016a0a90` | *(por resolver con `notion-get-users`; apareció como adviser de "XIT SPA" en Contable Febrero)* |

---

## 10 · IDs estables (referencia rápida)

| Recurso | ID / data source |
|---|---|
| Sandbox `General Customers Data - AuditAI` (**destino, escribible**) | db `16f12147-b3ea-8354-872b-814f104871b7` · ds `collection://4ff12147-b3ea-82f4-98dd-072067524cdc` |
| Original `General Customers Data` (**NO tocar**) | db `1a23f5e4-0223-46a6-9ad5-16ea823b64ba` · ds `690945e4-220a-48c3-a888-7fe9ae242d55` |
| Contable Mayo (aux, solo lectura) | db `37212147-b3ea-80fa-ab06-cfd9782372a9` · ds `fdb12147-b3ea-820b-8595-07535e078336` |
| Contable Febrero (aux, solo lectura) | db `3ae12147-b3ea-839d-b941-81946a083c62` · ds `e4c12147-b3ea-83f4-a4eb-07dabe205145` |
| RRHH JUNIO 2026 (aux, solo lectura) | db `38712147-b3ea-80f9-9484-e0ad99c94a26` · ds `9c512147-b3ea-8256-a570-871254c13b3d` |
| Backup previo sandbox | `backups/general-customers-data/2026-07-01_sandbox_pre-fase-A.csv` |
| Log de auditoría | `backups/general-customers-data/log-auditoria-volcado.csv` |

---

## 11 · Manejo del rate-limit de Notion (crítico)

La API limita a ~**3 req/s** y devuelve **HTTP 429** con `Retry-After` (segundos) al excederse (visto constantemente en este proyecto). Reglas:
- **Una consulta a la vez**; no disparar consultas en paralelo (el paralelo dispara 429).
- Al recibir 429 → esperar el `Retry-After` (típico 30 s) y reintentar. Se puede usar `ScheduleWakeup` (~35 s) para reintentar sin bloquear.
- Paginar lecturas grandes con `LIMIT 100 OFFSET n` (máx 100 por página).
- **Guardar cada página cruda en el scratchpad** (JSON) apenas llega, para no re-consultar si hay corte. Cruces y análisis se hacen **localmente** (Python), sin gastar cuota.

---

## 12 · Seguridad y PII (no negociable)

- **Destino de escritura: solo la sandbox.** Las bases mensuales y el original son **solo lectura**.
- **Nunca imprimir** en el chat ni en el repo valores de `RUT`, `CLAVE SII`, `email`, `USUARIO`/`CLAVE`, `Previred`, `Whatsapp`. Reportar solo **conteos, nombres (title) e IDs**. En el log de auditoría, la clave se anota como "(credencial - ver Notion)".
- Dry-run privado (con valores) va a `backups/` (git-ignored). Dry-run público (sin PII) puede mostrarse.
- Antes de escrituras masivas: **backup fresco** de la sandbox + **dry-run** + **confirmación del usuario** + **log**.
- Precedencia de valores en conflicto: **fuente auxiliar gana** (D21); entre meses, el **más reciente** gana para campos que cambian (clave/email).

---

## 13 · Entregables al terminar

1. Tabla completa de bases mensuales → data source IDs (§4 actualizado).
2. Resultado de los 4 objetivos: RUT encontrado (y en qué mes) o "no existe en ninguna base" con evidencia.
3. Diff de enriquecimiento general (cuántos `RUT`/`CLAVE SII`/`email`/`Adviser`/`CRM` se completaron/corrigieron).
4. Re-medición de completitud de la base (formato de [`14`](14-construccion-dataset-y-anomalias.md) §2).
5. Actualizar: §3 de este doc, [`14`](14-construccion-dataset-y-anomalias.md), [`11-checklist-maestro.md`](11-checklist-maestro.md) y [`08`](08-notion-general-customers-data.md) (completitud).

---

**Anterior:** [`14-construccion-dataset-y-anomalias.md`](14-construccion-dataset-y-anomalias.md) · **Volver al** [`README`](README.md)
