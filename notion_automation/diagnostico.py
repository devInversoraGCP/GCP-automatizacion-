"""Diagnóstico didáctico de los fallos de envío de correo (doc 27, observabilidad).

Convierte el `motivo` técnico de un fallo en dos explicaciones a medida:

- Para el ASESOR (contador, no dev): qué pasó en lenguaje simple, si lo puede
  resolver solo, y los pasos exactos en Notion.
- Para el DEV: causa raíz técnica, dónde mirar en el código, y una query lista
  para pegar en un chat con un LLM (como Claude) y resolverlo directo.

Módulo PURO: sin I/O ni dependencias del resto del backend, para poder testear
la clasificación y el contenido sin mocks. No maneja PII (no recibe el valor de
la celda Email, solo el nombre del cliente —razón social— y el page_id —UUID—).
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Diagnostico:
    """Resultado del diagnóstico de un fallo, con contenido para ambas audiencias."""
    categoria: str                       # slug estable: email_invalido, sin_email, bounce, ...
    titulo: str                          # titular corto y humano
    puede_asesor: bool                   # ¿el asesor lo puede resolver sin el dev?
    explicacion_asesor: str              # 1-2 frases en lenguaje simple
    pasos_asesor: list[str] = field(default_factory=list)   # pasos accionables en Notion
    causa_raiz: str = ""                 # una línea técnica (para el dev)
    detalle_dev: str = ""                # dónde mirar / qué revisar (para el dev)
    query_llm: str = ""                  # prompt copy-paste para resolver con un LLM


def _q(texto: str) -> str:
    """Colapsa espacios de una query multilinea para que quede en un bloque limpio."""
    return " ".join(texto.split())


def _clasificar_bounce(reason: str) -> tuple[str, bool, bool]:
    """Traduce el motivo técnico de SendGrid a una situación en lenguaje de
    contador. Devuelve (situacion_humana, transitorio, direccion_mala):

    - transitorio: hipo del servidor destino (DNS/MX/greylist/timeout). El
      sistema reintenta solo; el asesor no toca nada.
    - direccion_mala: la dirección no existe / está mal escrita (hard bounce).
      El asesor debe corregir la celda Email.
    (Si ninguno es True: buzón lleno o bloqueo, con su propia explicación.)
    """
    r = (reason or "").lower()
    # Transitorio primero: DNS/MX/PTR/greylist/timeout/códigos 4.x
    if any(s in r for s in ("mx", "dns", "ptr", "timeout", "try again",
                            "temporar", "greylist", "deferred", "4.2.", "421")):
        return ("El servidor de correo del cliente tuvo un problema temporal "
                "(no es la dirección en sí).", True, False)
    # Buzón lleno
    if any(s in r for s in ("full", "quota", "552", "insufficient storage")):
        return ("El buzón del cliente está lleno y por ahora no puede recibir "
                "más correos.", False, False)
    # Bloqueo / spam / política del dominio destino
    if any(s in r for s in ("block", "spam", "policy", "reputation", "blacklist",
                            "554", "content", "rejected due", "denied")):
        return ("El servidor del cliente bloqueó el correo (probable filtro de "
                "spam o política del dominio del cliente).", False, False)
    # Dirección inexistente / mal escrita (hard bounce clásico)
    if any(s in r for s in ("does not exist", "no such", "user unknown",
                            "unknown user", "mailbox unavailable", "invalid",
                            "550", "5.1.1", "not found", "recipient")):
        return ("La dirección de correo no existe o está mal escrita.", False, True)
    return ("El servidor del cliente devolvió el correo sin un motivo claro.",
            False, False)


def diagnosticar(
    motivo: str,
    *,
    flujo: str = "",
    cliente: str = "",
    periodo: str = "",
    page_id: str = "",
    asesor: str = "",
    extra: dict | None = None,
) -> Diagnostico:
    """Clasifica el `motivo` de un fallo y arma el Diagnostico. `extra` lleva
    contexto opcional (bounce_reason, ya_reintentado). Nunca lanza: ante algo no
    reconocido devuelve la categoría 'desconocido' (dev-first)."""
    extra = extra or {}
    m = (motivo or "").lower()
    cli = cliente or "el cliente"
    pid = page_id or "(sin page_id)"
    fl = flujo or "f29"

    # --- Rebote real: SendGrid aceptó pero el correo no llegó (bounce/dropped) ---
    if extra.get("bounce_reason") or "no llegó" in m or "no llego" in m or "bounce" in m or "no entregado" in m:
        reason = str(extra.get("bounce_reason", "") or "")
        ya = bool(extra.get("ya_reintentado"))
        situacion, transitorio, direccion_mala = _clasificar_bounce(reason)

        # Aclaración clave (confusión real de los asesores): "Enviado" en la fila
        # significa que el correo SALIÓ, no que el cliente lo recibió. La verdad
        # de si llegó está en la columna 'Entrega Correo' (✅ / ❌).
        reintento_txt = (
            " El sistema ya reintentó solo una vez y volvió a rebotar." if ya
            else " El sistema reintentará solo una vez más en unos minutos; si igual no llega, verás el ❌."
        ) if transitorio or not direccion_mala else ""

        # Pasos según el tipo de rebote (no todos se resuelven igual).
        if direccion_mala:
            pasos = [
                f"Abre la fila de {cli} en Notion y revisa la columna Email letra por letra "
                "(sin espacios, sin comas de más, dominio bien escrito).",
                "Confirma la dirección correcta con el cliente si tienes dudas.",
                "Corrige la celda Email y vuelve a apretar el botón de enviar.",
            ]
        elif transitorio:
            pasos = [
                "No necesitas hacer nada por ahora: fue un problema temporal del servidor del cliente "
                "y el sistema reintenta solo.",
                "Mira la columna 'Entrega Correo' de la fila en unos minutos: si queda en ✅ Entregado, llegó.",
                "Si al rato sigue en ❌, recién ahí confirma la dirección con el cliente y reenvía.",
            ]
        else:  # buzón lleno o bloqueo/spam
            pasos = [
                f"Contacta a {cli} por otro medio (teléfono/WhatsApp) y avísale que el correo no le llegó.",
                "Pídele que revise su carpeta de Spam/No deseado y que agregue a Contactos el remitente "
                "para que no lo bloquee; si el buzón estaba lleno, que libere espacio.",
                "Cuando lo confirme, vuelve a apretar el botón. Si vuelve a rebotar, avisa al equipo técnico.",
            ]

        return Diagnostico(
            categoria="bounce",
            titulo=f"El correo de {cli} salió pero NO le llegó al cliente (rebotó)",
            puede_asesor=True,
            explicacion_asesor=(
                "Importante: que la fila diga «Enviado» significa que el correo SALIÓ del sistema, "
                "NO que el cliente lo recibió. En este caso el correo salió pero rebotó (volvió sin "
                f"entregarse). Motivo: {situacion}"
                + reintento_txt
                + " Guíate siempre por la columna «Entrega Correo» de la fila: ✅ = llegó, ❌ = no llegó."
            ),
            pasos_asesor=pasos,
            causa_raiz=(
                "SendGrid emitió un evento bounce/dropped (aceptó el 202 pero el MTA destino "
                f"rechazó la entrega). Motivo SendGrid: {reason or 'sin detalle'}. "
                + ("Parece TRANSITORIO (DNS/MX): el reintento automático debería resolverlo."
                   if transitorio else
                   "Parece un HARD bounce (dirección/buzón): requiere corregir el dato."
                   if direccion_mala else
                   "Rebote por buzón lleno o bloqueo/spam del dominio destino: puede requerir contacto con el cliente.")
            ),
            detalle_dev=(
                f"flujo={fl} · page_id={pid}. El write-back de Status quedó en 'Enviado' "
                "(SendGrid había aceptado). El reintento único post-bounce está en "
                "app._agendar_reintento (REINTENTO_BOUNCE_S). La columna 'Entrega Correo' "
                "de la fila guarda el estado real."
            ),
            query_llm=_q(f"""
                En el proyecto AuditAI, el correo F29/{fl} de "{cli}" (page_id={pid}) rebotó.
                Motivo técnico de SendGrid: "{reason or 'sin detalle'}".
                (1) Dime si es un hard bounce (dirección/buzón inexistente) o transitorio (DNS/MX/timeout).
                (2) Con el MCP de Notion, fetch de la fila page_id={pid} y muéstrame el valor actual de Email
                (sin exponerlo en claro si es sensible).
                (3) Si el valor está mal, busca por el RUT del cliente en la base madre
                (General Customers Data) un correo válido y propón la corrección; pídeme confirmación antes de escribir.
            """),
        )

    # --- Asesor marcado como pendiente en asesores_smtp.json ---
    if "pendiente" in m and "asesor" in m:
        return Diagnostico(
            categoria="asesor_pendiente",
            titulo=f"La cuenta del asesor aún no está habilitada para enviar",
            puede_asesor=False,
            explicacion_asesor=(
                "El envío se hace desde la cuenta del asesor asignado, y esa cuenta todavía "
                "no quedó habilitada en el sistema. Esto lo resuelve el equipo técnico; no es "
                "un problema de la fila del cliente."
            ),
            pasos_asesor=[
                "No necesitas cambiar nada en Notion.",
                "Avisa al administrador que la cuenta del asesor está pendiente de habilitar.",
            ],
            causa_raiz="El asesor está marcado con \"pendiente\": true en asesores_smtp.json.",
            detalle_dev=(
                "Quitar el flag 'pendiente' del asesor en asesores_smtp(.local).json / "
                "ASESORES_SMTP_JSON, y verificar que su remitente esté validado en SendGrid."
            ),
            query_llm=_q(f"""
                En AuditAI, el asesor "{asesor or '(desconocido)'}" está marcado como 'pendiente'
                en asesores_smtp.json y por eso no puede enviar. Muéstrame su entrada en el JSON,
                confirma si su email de remitente está listo para verificar en SendGrid, y dame el
                cambio exacto para habilitarlo.
            """),
        )

    # --- Email inválido: la celda Email trae algo que no es un correo ---
    if ("direccion de correo" in m or "dirección de correo" in m
            or "does not contain a valid address" in m or "valid address" in m):
        return Diagnostico(
            categoria="email_invalido",
            titulo=f"El correo de {cli} en Notion no es una dirección válida",
            puede_asesor=True,
            explicacion_asesor=(
                "La columna Email de la fila tiene algo que no es un correo: puede ser un RUT, "
                "un nombre de usuario, o texto suelto que se pegó por error en esa celda. Por eso "
                "el sistema no pudo enviar (y así evitó mandar un correo a una dirección inválida)."
            ),
            pasos_asesor=[
                f"Abre la fila de {cli} en Notion y ve a la columna Email.",
                "Deja SOLO el correo del cliente, con el formato nombre@dominio.cl "
                "(sin RUT, sin usuario, sin espacios).",
                "Si el cliente recibe en varias direcciones, escríbelas separadas por coma: "
                "uno@empresa.cl, dos@empresa.cl",
                "Guarda y vuelve a apretar el botón de enviar.",
            ],
            causa_raiz=(
                "El valor de Email no pasó email_sender._validar_destinatarios (no matchea la "
                "regex de dirección única). SendGrid habría respondido HTTP 400 "
                "'Does not contain a valid address'."
            ),
            detalle_dev=(
                f"flujo={fl} · page_id={pid}. El motivo NO incluye el valor de la celda (política "
                "sin PII en logs). El valor real hay que verlo con un fetch de la fila."
            ),
            query_llm=_q(f"""
                En AuditAI, la fila de Notion page_id={pid} (cliente "{cli}", flujo {fl}) tiene la
                columna Email con un valor que NO es un correo válido.
                (1) Con el MCP de Notion, fetch de esa fila y muéstrame el valor actual de Email.
                (2) Busca por el RUT del cliente en la base madre (General Customers Data) si hay un
                correo válido cargado.
                (3) Propón el valor corregido para la columna Email y, si lo confirmo, aplícalo con
                update-page. No toques ninguna otra columna.
            """),
        )

    # --- Sin email en ninguna base ---
    if "sin email" in m or "sin correo" in m or "base central" in m:
        return Diagnostico(
            categoria="sin_email",
            titulo=f"{cli} no tiene correo cargado en ninguna base",
            puede_asesor=True,
            explicacion_asesor=(
                "La fila del cliente no tiene correo en la columna Email, y tampoco lo encontramos "
                "en la base de datos general buscando por su RUT. Sin una dirección, el sistema no "
                "tiene a dónde enviar."
            ),
            pasos_asesor=[
                f"Consigue el correo de {cli} (pregúntale al cliente, revisa su contrato o ficha).",
                "Escríbelo en la columna Email de la fila.",
                "Vuelve a apretar el botón de enviar.",
            ],
            causa_raiz=(
                "props Email vacío y nc.buscar_email_en_central(rut) devolvió None: no hay dato "
                "de correo para este cliente en la fila ni en General Customers Data."
            ),
            detalle_dev=f"flujo={fl} · page_id={pid}. Confirmar que el RUT de la fila esté bien cargado (el lookup filtra por RUT).",
            query_llm=_q(f"""
                En AuditAI, el cliente "{cli}" (fila page_id={pid}) no tiene correo ni en su fila ni
                en la base madre. Con el MCP de Notion, busca en todo el workspace (search) cualquier
                correo asociado a este cliente o su RUT, y dame los candidatos que encuentres. Si hay
                uno confiable, propón el update de la columna Email de page_id={pid}.
            """),
        )

    # --- Sin mes (no se puede calcular la fecha límite) ---
    if "sin mes" in m or "fecha límite" in m or "fecha limite" in m or "month" in m:
        return Diagnostico(
            categoria="sin_mes",
            titulo="No se pudo determinar el período (mes) del F29",
            puede_asesor=True,
            explicacion_asesor=(
                "El sistema necesita saber el mes del F29 para calcular la fecha límite de pago, y "
                "no lo pudo deducir: ni la columna Month de la fila ni el nombre de la base lo dicen."
            ),
            pasos_asesor=[
                "Revisa que la columna Month de la fila tenga el período, por ejemplo 'Junio 2026'.",
                "O confirma que la base se llame 'Contable <Mes>' (ej: 'Contable Junio').",
                "Corrige lo que falte y vuelve a apretar el botón.",
            ],
            causa_raiz="fecha_limite() no pudo parsear el mes: Month vacío y derivar_month_desde_base('') vacío.",
            detalle_dev=f"flujo={fl} · page_id={pid}. Ver derivar_month_desde_base y el título de la base parent.",
            query_llm=_q(f"""
                En AuditAI, la fila page_id={pid} ("{cli}") no tiene mes deducible. Con el MCP de
                Notion, fetch de la fila y de su base parent, muéstrame el valor de Month y el título
                de la base, y dime qué corregir para que derivar_month_desde_base funcione.
            """),
        )

    # --- Remitente no verificado en SendGrid (403) ---
    if "403" in m or "no verificado" in m or "verificado en sendgrid" in m or "single sender" in m:
        return Diagnostico(
            categoria="remitente_no_verificado",
            titulo="Problema de configuración del sistema (remitente no verificado)",
            puede_asesor=False,
            explicacion_asesor=(
                "Este no es un problema de la fila del cliente, sino de la configuración del correo "
                "del asesor en el sistema de envíos. Ya está avisado el equipo técnico; no necesitas "
                "hacer nada."
            ),
            pasos_asesor=["No cambies nada en Notion.", "El equipo técnico lo resuelve."],
            causa_raiz="SendGrid 403: el remitente (email del asesor) no está verificado (Single Sender o Domain Auth).",
            detalle_dev=(
                "Verificar Single Sender del asesor en SendGrid, o completar Domain Auth de "
                "inversoragcp.com. Revisar que asesores_smtp.json use un remitente verificado."
            ),
            query_llm=_q(f"""
                En AuditAI, SendGrid devolvió 403 (remitente no verificado) para el asesor
                "{asesor or '(desconocido)'}". Revisa notion_automation/asesores_smtp.json para ese
                asesor y dame los pasos exactos para verificar su Single Sender o el Domain Auth de
                inversoragcp.com en SendGrid.
            """),
        )

    # --- Falta configuración de envío (sin API key / sin app password) ---
    if "sendgrid_api_key" in m or "app password" in m:
        return Diagnostico(
            categoria="config",
            titulo="Falta configuración de envío en el servidor",
            puede_asesor=False,
            explicacion_asesor=(
                "El sistema no tiene configurado el servicio de envío de correos. Esto lo resuelve "
                "el equipo técnico; no es un problema de la fila."
            ),
            pasos_asesor=["No cambies nada en Notion.", "Avisa al administrador."],
            causa_raiz="Ni SENDGRID_API_KEY (nube) ni App Password SMTP (local) disponibles.",
            detalle_dev="Setear SENDGRID_API_KEY en Render (Environment) o el App Password del asesor en asesores_smtp.local.json.",
            query_llm=_q("""
                En AuditAI falta la configuración de envío (SENDGRID_API_KEY o App Password).
                Revisa render.yaml y el flujo de carga de credenciales (email_sender._cargar_asesores)
                y dame el checklist exacto de variables de entorno que deben estar seteadas.
            """),
        )

    # --- Sin título/nombre del cliente (RRHH/Tickets) ---
    if "sin cliente" in m or "sin customers" in m or "sin tarea" in m or "necesario para el asunto" in m:
        return Diagnostico(
            categoria="sin_titulo",
            titulo="La fila no tiene nombre de cliente",
            puede_asesor=True,
            explicacion_asesor=(
                "La fila no tiene cargado el nombre del cliente, que se usa en el asunto y el cuerpo "
                "del correo. Sin ese dato el correo quedaría incompleto."
            ),
            pasos_asesor=[
                "Abre la fila en Notion y completa el nombre del cliente (columna de título).",
                "Vuelve a apretar el botón de enviar.",
            ],
            causa_raiz="El campo título (CLIENTE/Customers/Tarea) llegó vacío.",
            detalle_dev=f"flujo={fl} · page_id={pid}.",
            query_llm=_q(f"""
                En AuditAI, la fila page_id={pid} no tiene título/nombre de cliente. Con el MCP de
                Notion, fetch de la fila y dime qué campo de título está vacío y con qué valor
                debería completarse.
            """),
        )

    # --- Sin monto de imposiciones (RRHH): el dato principal del correo ---
    # El gate lo agregó handlers/rrhh.py el 31-jul (no mandar $0 cuando la celda
    # está vacía), pero el motivo nunca se clasificó acá: caía en 'desconocido',
    # que le dice al asesor "vuelve a apretar el botón" — o sea, lo mandaba a
    # repetir el mismo fallo en vez de cargar el monto. Cada repetición son 2
    # correos más (asesor + dev). Ver el bucle detectado el 05-ago-2026.
    if "monto imposiciones" in m or "sin monto" in m or "dato principal del correo" in m:
        return Diagnostico(
            categoria="sin_monto",
            titulo=f"Falta el monto de imposiciones de {cli}",
            puede_asesor=True,
            explicacion_asesor=(
                "La fila no tiene cargado el monto de imposiciones, que es justamente el dato "
                "que el correo le informa al cliente. El sistema prefirió no enviar antes que "
                "mandar un aviso en $0, que le diría al cliente que no debe nada."
            ),
            pasos_asesor=[
                f"Abre la fila de {cli} en la planilla de RRHH del mes y ve a la columna "
                "«MONTO IMPOSICIONES|».",
                "Carga el monto del mes (si el cliente efectivamente no debe imposiciones, "
                "escribe un 0: un cero cargado a mano sí se envía).",
                "Recién ahí vuelve a apretar el botón de enviar. Si lo aprietas sin cargar el "
                "monto, va a fallar de nuevo igual.",
            ],
            causa_raiz=(
                "nc.plain(props['MONTO IMPOSICIONES|']) == '' (number is None): la celda está "
                "vacía. Gate en handlers/rrhh.py; vacío ≠ cero explícito, por diseño."
            ),
            detalle_dev=(
                f"flujo={fl} · page_id={pid}. No es un bug del backend: es un dato faltante en "
                "la planilla. Si se repite en muchas filas del mes, probablemente la base RRHH "
                "del mes nuevo aún no fue llenada (o pasó un /reset-mes) y los asesores están "
                "apretando el botón sobre filas en blanco."
            ),
            query_llm=_q(f"""
                En AuditAI, la fila de RRHH page_id={pid} ("{cli}") no tiene cargada la columna
                «MONTO IMPOSICIONES|» y por eso no se envió el correo. Con el MCP de Notion,
                fetch de esa fila y de su base parent, y dime: (1) si la celda del monto está
                realmente vacía, (2) cuántas filas más de esa misma base están sin monto, y
                (3) si la base corresponde al mes vigente. No escribas nada en Notion.
            """),
        )

    # --- Fallback: no reconocido (dev-first) ---
    return Diagnostico(
        categoria="desconocido",
        titulo=f"No se pudo enviar el correo de {cli}",
        puede_asesor=False,
        explicacion_asesor=(
            "Ocurrió un problema al enviar que el sistema no pudo clasificar. Ya está avisado el "
            "equipo técnico, que lo va a revisar."
        ),
        pasos_asesor=[
            "Puedes volver a intentar apretando el botón una vez más.",
            "Si vuelve a fallar, espera a que el equipo técnico lo revise.",
        ],
        causa_raiz=f"Motivo no clasificado: {motivo!r}",
        detalle_dev=f"flujo={fl} · page_id={pid}. Revisar logs del backend (auditai.log) alrededor del page_id.",
        query_llm=_q(f"""
            En AuditAI falló el envío del correo de "{cli}" (page_id={pid}, flujo {fl}) con un motivo
            no clasificado: "{motivo}". Ayúdame a encontrar la causa: revisa el flujo del handler
            correspondiente y los logs alrededor de ese page_id, y propón el fix.
        """),
    )
