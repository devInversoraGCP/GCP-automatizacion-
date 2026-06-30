# 04 · Glosario

> Términos tributarios y técnicos usados en el proyecto. Pensado para consulta rápida desde los demás documentos.

## Términos tributarios

| Término | Definición |
|---------|------------|
| **SII** | Servicio de Impuestos Internos: la autoridad tributaria de Chile. |
| **F29 / Formulario 29** | Declaración mensual de IVA, PPM y retenciones. Tiene ~140 códigos (casillas). |
| **IVA** | Impuesto al Valor Agregado. Tasa general en Chile: **19%**. |
| **IVA débito fiscal** | IVA cobrado en las **ventas**. Es lo que la empresa debe al fisco por vender. |
| **IVA crédito fiscal** | IVA pagado en las **compras**. Se descuenta del débito. |
| **IVA determinado** | Débito − Crédito (− remanente). Positivo ⇒ se paga; negativo ⇒ saldo a favor. |
| **Remanente de crédito fiscal** | Saldo de crédito a favor que sobra y se **arrastra** al mes siguiente (código 77 en el caso actual). |
| **PPM** | Pago Provisional Mensual: anticipo del impuesto a la renta, % sobre las ventas netas (código 62). |
| **Retención** | Monto que la empresa retiene por cuenta de un tercero y entera al fisco. |
| **Retención de honorarios** | Retención sobre boletas de honorarios de profesionales (Ley 21.133, código 151). |
| **Retención de impuesto único** | Retención del impuesto único a los trabajadores (código 48). |
| **Base imponible** | Monto neto sobre el que se aplica una tasa de impuesto. |
| **Tasa** | Porcentaje que se aplica a la base (ej. IVA 19%, PPM 0,125%, honorarios 14,5%). |
| **Afecto / Exento** | Operación gravada con IVA (afecto) vs. no gravada (exento). |
| **RCV** | Registro de Compras y Ventas: el repositorio del SII con los documentos electrónicos; base de su propuesta de F29. |
| **DTE** | Documento Tributario Electrónico (facturas, notas, boletas electrónicas). |
| **Factura** | Documento principal de una venta o compra afecta a IVA. |
| **NC — Nota de Crédito** | Documento que rebaja o anula una operación previa. |
| **ND — Nota de Débito** | Documento que aumenta el valor de una operación previa. |
| **DIN** | Declaración de Ingreso: documento de importación de bienes. |
| **Comprobante de pago electrónico** | Comprobante de transacciones pagadas por medios electrónicos; genera débito en el caso `CLIENTE1`. |
| **Propuesta del SII** | Borrador del F29 que el SII prellena a partir del RCV. AuditAI la usa como contraparte de auditoría. |

## Términos técnicos / del proyecto

| Término | Definición |
|---------|------------|
| **Motor de cálculo** | Componente que implementa las 6 partes y produce el resultado del F29 a partir de los datos. |
| **Ingesta** | Etapa de lectura y carga de los datos de origen (libros de compra/venta, remanente). |
| **Normalización** | Limpieza y estandarización de los datos (codificación UTF-8, formatos de monto y fecha). |
| **Mapeo de códigos** | Traducción de los totales internos a los códigos oficiales del F29. |
| **Conciliación / auditoría** | Comparación del cálculo propio contra la propuesta del SII, código por código. |
| **Golden test** | Prueba automática que verifica que el motor reproduce un resultado conocido (el de `CLIENTE1`). |
| **Determinista** | Que ante las mismas entradas produce siempre la misma salida (propiedad exigida al cálculo del impuesto). |

---

**Anterior:** [`03-estado-del-arte.md`](03-estado-del-arte.md) · **Siguiente:** [`05-decisiones-y-preguntas.md`](05-decisiones-y-preguntas.md)
