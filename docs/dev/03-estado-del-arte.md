# 03 · Estado del arte: cómo se resuelve hoy

> Panorama de las soluciones existentes para armar el F29, y dónde encaja AuditAI. Sirve para posicionar el diferencial del proyecto frente a lo que ya hay en el mercado.

## Cómo se declara el F29 hoy

Existen, a grandes rasgos, tres caminos para llegar al F29 de cada mes:

### 1. La propuesta automática del SII
El propio SII, a partir del **Registro de Compras y Ventas (RCV)** que se alimenta de los documentos tributarios electrónicos, **propone un borrador del F29** ya con varias casillas prellenadas.

- **Fortaleza:** es gratuito, oficial y reduce el trabajo de transcripción.
- **Límite:** es una propuesta; el contribuyente sigue siendo responsable de revisarla, ajustarla y validar que esté correcta. No "audita" nada por ti ni explica diferencias.
- **Clave para AuditAI:** no competimos con la propuesta del SII — la **usamos como contraparte de auditoría**. Es justamente el "segundo origen" contra el cual conciliar nuestro cálculo propio.

### 2. Software contable
Suites contables como **Nubox, Defontana, LioRen, Bsale** (y otras) generan el F29 como una función más dentro de un sistema de contabilidad completo y de pago.

- **Fortaleza:** integran todo el ciclo contable (facturación, libros, remuneraciones, etc.).
- **Límite:** son sistemas amplios y de costo recurrente; el cálculo del F29 es una pieza dentro de un producto grande, no su foco. La auditoría explicada contra la propuesta del SII no es, en general, su propuesta de valor central.

### 3. Planillas Excel manuales
El método del caso actual ([`PRUEBA1.xlsx`](../../PRUEBA1.xlsx)): un contador arma el cálculo en una hoja de cálculo y cuadra a mano contra el SII.

- **Fortaleza:** flexible, barato, totalmente bajo control del profesional.
- **Límite:** frágil (una fórmula rota pasa inadvertida), no escala a muchos clientes y el cuadre contra el SII es 100% manual y propenso a error.

## Comparativa

| | Propuesta SII | Software contable | Excel manual | **AuditAI** |
|---|:---:|:---:|:---:|:---:|
| Calcula el F29 automáticamente | Parcial | ✅ | ❌ (manual) | ✅ |
| **Audita contra la propuesta del SII** | ❌ | Parcial | ❌ (manual) | ✅ **(foco)** |
| Explica las diferencias en lenguaje natural | ❌ | ❌ | ❌ | ✅ **(IA)** |
| Rastrea cada cifra hasta su documento | ❌ | Parcial | ❌ | ✅ |
| Costo | Gratis | Suscripción | Bajo | Por definir |
| Foco | Recaudación | Contabilidad integral | Flexibilidad | **Auditoría + explicación** |

> Nota: los nombres de productos se citan como referencia general del panorama. Sus capacidades específicas cambian con el tiempo; conviene verificarlas antes de usarlas en material externo o comercial.

## Dónde encaja AuditAI (el diferencial)

AuditAI **no busca ser otra suite contable**. Su apuesta es ocupar una capa que hoy nadie cubre bien:

> **Auditoría/conciliación automática del F29 + explicación con IA.**

Es decir: tomar el cálculo (propio o de cualquier origen), confrontarlo automáticamente contra la propuesta del SII, y cuando algo no cuadre, **decir en qué código y por qué**, en lenguaje que un contador acepte sin rehacer el cálculo a mano.

Principio que delimita el alcance de la IA: **la IA explica y detecta anomalías; no decide el monto.** El número del impuesto siempre sale de reglas deterministas y auditables (ver [`00-introduccion.md`](00-introduccion.md) y [`../ARQUITECTURA.md`](../ARQUITECTURA.md)). Esto es lo que hace al producto confiable para un contexto tributario.

---

**Anterior:** [`02-estado-del-proyecto.md`](02-estado-del-proyecto.md) · **Siguiente:** [`04-glosario.md`](04-glosario.md)
