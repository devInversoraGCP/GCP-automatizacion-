"""Carga (o actualiza) la App Password de un asesor en asesores_smtp.json de forma segura.

- Pide la contraseña por consola SIN mostrarla (getpass) -> no queda en pantalla ni en historiales.
- PRUEBA el login SMTP contra Gmail ANTES de guardar: si Google la rechaza, no guarda nada.
- Si el login funciona, guarda la password y marca pendiente=False.

Uso:
  python set_asesor_password.py                       # pregunta el email
  python set_asesor_password.py carloscereceda@inversoragcp.com
"""
from __future__ import annotations
import sys, json, ssl, smtplib, getpass, pathlib

JSON = pathlib.Path(__file__).parent / "asesores_smtp.json"


def main() -> None:
    data = json.load(open(JSON, encoding="utf-8"))
    asesores = [k for k in data if not k.startswith("_")]

    email = sys.argv[1] if len(sys.argv) > 1 else input("Email del asesor: ").strip()
    if email not in data:
        print(f"[!] '{email}' no existe en asesores_smtp.json.")
        print("    Asesores disponibles:", asesores)
        sys.exit(1)

    try:
        pw = getpass.getpass(f"Pega la App Password de {email} (no se mostrara): ")
    except Exception:
        pw = input(f"Pega la App Password de {email}: ")
    pw = (pw or "").replace(" ", "")
    if not pw:
        print("Cancelado: no se ingreso contraseña.")
        sys.exit(1)

    print("Probando login SMTP contra Gmail (no se envia ningun correo)...")
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=25) as s:
            s.login(email, pw)
    except smtplib.SMTPAuthenticationError:
        print("[X] Google RECHAZO la contraseña (error 535). NO se guardo nada.")
        print("    Revisa: (1) la cuenta tiene verificacion en 2 pasos activada,")
        print("            (2) la App Password se copio completa (16 caracteres).")
        sys.exit(1)
    except Exception as exc:
        print(f"[X] Error de conexion ({type(exc).__name__}): {str(exc)[:150]}. No se guardo.")
        sys.exit(1)

    data[email]["password"] = pw
    data[email]["pendiente"] = False
    data[email]["app_password"] = True
    json.dump(data, open(JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[OK] Login exitoso. Password guardada y {email} marcado como activo (pendiente=False).")


if __name__ == "__main__":
    main()
