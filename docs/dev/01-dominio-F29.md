# 01 · El dominio: Formulario 29 e IVA chileno (para desarrolladores)

> Documento núcleo. Su objetivo es que un desarrollador **sin conocimiento de impuestos chilenos** pueda entender qué calcula AuditAI y por qué, usando el caso real [`CLIENTE1`](../../PRUEBA1.xlsx) como ejemplo trabajado de principio a fin.

## 1. El contexto: SII y Formulario 29

- **SII** = Servicio de Impuestos Internos, la autoridad tributaria de Chile.
- **Formulario 29 (F29)** = la declaración **mensual** que presenta una empresa para informar y pagar, principalmente, el **IVA**, más los **PPM** (pagos provisionales) y ciertas **retenciones**. El formulario oficial está en [`F29.pdf`](../../F29.pdf) y tiene unos **140 códigos** numerados (cada casilla es un "código").
- El SII genera automáticamente una **propuesta** del F29 a partir de los documentos electrónicos que ya conoce. Esa propuesta es la **contraparte que AuditAI usa para auditar** el cálculo propio.

## 2. Conceptos clave del IVA

El IVA (Impuesto al Valor Agregado) en Chile tiene una **tasa del 19%**. La idea central es simple:

| Concepto | Qué es | En el negocio |
|----------|--------|---------------|
| **IVA débito fiscal** | El IVA que la empresa **cobró** en sus ventas | Lo que la empresa le "debe" al fisco por vender |
| **IVA crédito fiscal** | El IVA que la empresa **pagó** en sus compras | Lo que la empresa puede descontar por comprar |
| **IVA determinado** | Débito − Crédito | Si es **positivo** → se paga IVA. Si es **negativo** → queda saldo a favor |
| **Remanente de crédito** | Saldo a favor de meses anteriores que se **arrastra** | Reduce el IVA a pagar de este mes |

Otros tributos que también van en el F29:
- **PPM** (Pago Provisional Mensual): un anticipo del impuesto a la renta, calculado como un porcentaje de las ventas netas.
- **Retenciones**: montos que la empresa retiene por cuenta de terceros — por ejemplo, **retención de honorarios** (boletas de profesionales) y **retención de impuesto único** (a trabajadores).

## 3. Las 6 partes del cálculo (la lógica central)

La planilla [`CLIENTE1`](../../PRUEBA1.xlsx) organiza el cálculo en 6 bloques, descritos en [`CONTEXT.md`](../../CONTEXT.md). Formalizados como reglas:

| Parte | Nombre | Regla (entrada → salida) | Celda Excel |
|-------|--------|--------------------------|-------------|
| **P1** | Documentos emitidos (débito) | Σ IVA de ventas (facturas, comprobantes electrónicos, notas de crédito) | `=SUM(D9:D11)` |
| **P2** | Documentos recibidos (crédito) | −Σ IVA de compras (facturas, notas de débito, DIN) | `=-SUM(D13:D15)` |
| **P3** | Remanente de crédito | Saldo a favor del período anterior (se arrastra, en negativo) | `=+G10*-1` |
| **P4** | IVA determinado | **P1 + P2 + P3** | `=+E12+E16+E17` |
| **P5** | Otros impuestos y retenciones | PPM + retención honorarios + retención impuesto único | varias |
| **P6** | Total mensual a pagar | **condicional** (ver abajo) | `=SUM(E23:E25)` |

### ⚠️ La regla condicional de la Parte 6 (la más fácil de equivocar)

> **Si P4 (IVA determinado) > 0:** Total = P4 + P5.
> **Si P4 ≤ 0:** Total = solo P5. El saldo a favor (P4 negativo) **no** reduce los otros impuestos; se **arrastra como remanente** al mes siguiente, pero el PPM y las retenciones **se pagan igual**.

Este `if` es el error manual más común y la razón de ser de gran parte de la auditoría. El motor de cálculo debe implementarlo explícitamente.

## 4. Ejemplo trabajado completo: `CLIENTE1`, período ABRIL

Datos reales de la planilla (tipo de IVA: afecto; plazo de pago: 20-may-2026):

```
P1 · Débito fiscal (ventas)
     Comprobantes pago electrónicos: 3 docs → IVA  $462
     TOTAL IVA VENTAS ........................  $462

P2 · Crédito fiscal (compras)
     Facturas de compra: 11 docs → IVA  $260.143
     TOTAL IVA RECUPERABLE ............... −$260.143

P3 · Remanente de crédito del mes anterior
     Remanente arrastrado ................ −$158.117

P4 · IVA determinado = P1 + P2 + P3
     462 − 260.143 − 158.117 ............. −$417.798   ⟶  negativo: NO se paga IVA,
                                                            se arrastra como remanente

P5 · Otros impuestos
     PPM: base = ventas netas = 462 / 0,19 = $2.432
          tasa = 0,125%  →  2.432 × 0,00125 ≈  $3
     Retención honorarios (14,5%) ............  $0
     Retención impuesto único ...............  $0

P6 · Total a pagar = (P4 ≤ 0) ⟹ solo P5
     TOTAL MENSUAL A CANCELAR ...............  $3
```

**Resultado:** la empresa no paga IVA este mes (tiene un saldo a favor de $417.798 que se arrastra), pero sí paga **$3** de PPM. La planilla original anota *"P Verificado con la propuesta del SII"* — es decir, este resultado fue cuadrado a mano contra el SII. **Automatizar ese cuadre es el objetivo de AuditAI.**

> Estos cinco números —**$462, $260.143, $158.117, −$417.798 y $3**— son el *golden test* del motor de cálculo (Fase 2): cualquier implementación debe reproducirlos exactamente. Ver [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md) y [`../ROADMAP.md`](../ROADMAP.md).

## 5. Mapeo a códigos del F29

Los totales internos deben traducirse a los códigos del formulario oficial. La planilla `CLIENTE1` ya mapea estos (columna de "CODIGO F29"):

| Código | Significado (según la planilla) | Valor en el ejemplo |
|--------|----------------------------------|---------------------|
| **62** | PPM neto determinado | (PPM del período) |
| **48** | Retención impuesto único a trabajadores | 0 |
| **151** | Retención Ley 21.133 (honorarios) | 0 |
| **77** | Remanente de crédito fiscal | $158.117 |

Además, en el F29 oficial ([`F29.pdf`](../../F29.pdf)) aparecen los códigos de totales de IVA que el motor deberá poblar, por ejemplo **538** (Total Débitos) y **537** (Total Créditos).

> ⚠️ **Pendiente (Fase 1):** el diccionario **completo y verificado** de los ~140 códigos del F29 —cada código con su significado y de qué documento se alimenta— es trabajo de la siguiente iteración. La tabla de arriba cubre solo los códigos que usa el caso actual y debe verificarse contra la normativa antes de usarse en producción.

## 6. Tipos de documento (vocabulario)

Para clasificar correctamente (paso 3 de la arquitectura), conviene conocer los documentos que entran al cálculo:

- **Factura de venta / de compra**: documento principal de venta o adquisición afecta a IVA.
- **Comprobante de pago electrónico**: el que genera el débito en el ejemplo `CLIENTE1`.
- **Nota de crédito (NC)**: rebaja o anula una venta/compra previa.
- **Nota de débito (ND)**: aumenta el valor de una operación previa.
- **DIN** (Declaración de Ingreso): documento de importación.

Definiciones rápidas de todos los términos en [`04-glosario.md`](04-glosario.md).

---

**Anterior:** [`00-introduccion.md`](00-introduccion.md) · **Siguiente:** [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md)
