# Spike F29 · Prueba de automatización de punta a punta

> **Prototipo (spike)** — adelanta la Etapa B2 ("muestras reales") como prueba de concepto.
> No es el motor definitivo ni cierra el gate del Frente A (D18).

## Qué prueba

Que el sistema es capaz de, **sin intervención manual**:

1. Leer RUT + Clave SII del cliente desde la base central de Notion (paso 0.1 de la spec [`17`](../docs/dev/17-especificacion-literal-calculo-f29.md)).
2. Entrar al SII con esas credenciales (navegador visible, supervisado).
3. Extraer del RCV el período indicado: P1 (débito), P2 (crédito), BI (neto + exento).
4. Calcular P4/P5/P6 con aritmética `Decimal` exacta y mapear a casillas del F29.

**Validación (golden test):** se corre con el período **2026-04 del Cliente 1** y se compara
el resultado contra la planilla ya validada con el SII. **Regla de no-trampa:** este código
no contiene ningún valor del golden test; extrae y calcula todo por su cuenta.
`PRUEBA1.xlsx`/`.csv` no se leen jamás desde aquí.

## Seguridad

- 🔒 Credenciales: solo en memoria, leídas de Notion vía `NOTION_TOKEN` (variable de entorno).
  **Nunca** se imprimen, loguean ni escriben a disco.
- 🛑 `sii_robot.py` tiene una **lista negra de botones** (`enviar|declarar|pagar|firmar|rectificar`):
  el robot se niega a clickear cualquier elemento que calce, en cualquier flujo.
- 📄 Todo lo descargado del SII va a `spike_f29/data/` (ignorado por git — contiene PII).
- ⚠️ Un solo intento de login: si falla, aborta (intentos repetidos bloquean la clave).

## Uso

```powershell
# 1. Preparar entorno (una vez)
python -m venv .venv
.venv\Scripts\pip install playwright
.venv\Scripts\playwright install chromium

# 2. Correr (navegador visible)
.venv\Scripts\python main.py --cliente "<NOMBRE EN LA BASE>" --periodo 2026-04 `
    --remanente 158117 --tasa 0.125
```

`--remanente` y `--tasa` son **entradas** (casillas 504 y 115 del período): para un período ya
declarado no existe "propuesta" en el SII, así que se pasan a mano (leídas del F29 declarado).
Con `--m3` el robot intenta leerlas en vivo de la propuesta del período actual (solo lectura,
supervisado).
