import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from crypto import decrypt_secret

logger = logging.getLogger("email_service")


def send_smtp_email(config: dict, subject: str, html_content: str, text_content: str = ""):
    """
    Sends an email using the company's configured SMTP server details in `config`.

    TLS policy: if the server does not OFFER STARTTLS (SMTPNotSupportedError)
    the send continues with a warning (legacy internal relays); but if the
    STARTTLS handshake FAILS mid-way, the send is ABORTED — the SMTP
    credentials must never travel over a plaintext connection.
    """
    smtp_host = config.get("smtp_host")
    smtp_port = config.get("smtp_port") or 587
    smtp_username = config.get("smtp_username")
    raw_password = config.get("smtp_password")
    smtp_password = decrypt_secret(raw_password) if raw_password else None
    smtp_from_email = config.get("smtp_from_email")
    smtp_to_email = config.get("smtp_to_email")

    if not smtp_host or not smtp_username or not smtp_password:
        logger.info("[SMTP] Servidor SMTP no configurado completamente para esta empresa. Omitiendo envío de correo.")
        return False

    from_addr = smtp_from_email or smtp_username
    to_addr = smtp_to_email
    if not to_addr:
        logger.warning("[SMTP] Destinatario de correo (smtp_to_email) no configurado. Omitiendo.")
        return False

    server = None
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        # Setup SMTP connection
        port = int(smtp_port)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_host, port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, port, timeout=15)
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                # Server does not offer STARTTLS — the admin chose this server
                # (typically an internal relay); continue with a loud warning.
                logger.warning(
                    "[SMTP] %s:%s no soporta STARTTLS. Enviando SIN cifrado — aceptable solo para relays internos.",
                    smtp_host, port,
                )
            except Exception as tls_err:
                # Handshake failed: abort instead of leaking credentials
                logger.error(
                    "[SMTP] Fallo el handshake STARTTLS con %s:%s (%s). Envío abortado para no exponer credenciales.",
                    smtp_host, port, tls_err,
                )
                return False

        server.login(smtp_username, smtp_password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        logger.info("[SMTP] Correo enviado exitosamente a %s bajo el asunto: '%s'", to_addr, subject)
        return True
    except Exception as e:
        logger.error("[SMTP Error] Fallo al enviar correo a %s: %s", to_addr, e)
        return False
    finally:
        # Always close the socket — previously an exception after connect()
        # leaked the SMTP connection.
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
