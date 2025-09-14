import html
from email.header import decode_header
import logging
import re
from datetime import datetime, timedelta, timezone
from email.message import Message
from typing import Optional

logger = logging.getLogger("imap-telegram-forwarder:parse")
logger.setLevel(logging.ERROR)


def extract_text_from_email(msg: Message) -> str:
    if msg.is_multipart():
        plain_chunks = []
        html_chunks = []
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    plain_chunks.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8",
                                                                             errors="replace"))
                except Exception:
                    plain_chunks.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
            elif ctype == "text/html" and "attachment" not in disp:
                try:
                    html_chunks.append(part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8",
                                                                            errors="replace"))
                except Exception:
                    html_chunks.append(part.get_payload(decode=True).decode("utf-8", errors="replace"))
        if plain_chunks:
            return "\n".join(plain_chunks).strip()
        if html_chunks:
            combined = "\n".join(html_chunks)
            return html_to_text(combined).strip()
        return ""
    else:
        ctype = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if not payload:
            return ""
        try:
            text = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            text = payload.decode("utf-8", errors="replace")
        if ctype == "text/plain":
            return text.strip()
        elif ctype == "text/html":
            return html_to_text(text).strip()
        else:
            return text.strip()


def html_to_text(html_content: str) -> str:
    """
    Очень простой конвертер html в текст: пока достаточно (я не хочу парсить(((()
    :param html_content: текст в формате html
    :return: текст читаемый
    """
    text = re.sub(r"<head.*?>.*?</head>", "", html_content, flags=re.S | re.I)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text


def make_telegram_text(msg_obj: Message) -> Optional[str]:
    """
    Форматирует текст в нужный телеграму
    :param msg_obj: сообщение начальное
    :return: сообщение отформатированное
    """
    subj = msg_obj.get("Subject", "(no subject)")
    frm = msg_obj.get("From", "(unknown sender)")
    date = msg_obj.get("Date", "")
    body = extract_text_from_email(msg_obj)
    preview = body.strip().splitlines()

    if preview:
        preview_text = "\n".join(preview[:10])
        if len(preview_text) > 600:
            preview_text = preview_text[:600] + "…"
    else:
        preview_text = "(no text body)"

    escaped_date = escape_html(date)
    parsed_date = parse_email_date(escaped_date)

    if datetime.now(timezone.utc) - parsed_date > timedelta(days=5):
        return

    text = (f"<b>{decode_subj(escape_html(subj))}</b>\n"
            f"From: {re.search(r"&lt;(.*)&gt;", escape_html(frm)).group(1)}\n"
            f"Date: {parsed_date}\n"
            f"\n"
            f"{escape_html(preview_text)}")
    return text


def escape_html(s: str) -> str:
    return html.escape(s)


def decode_subj(subj: str) -> str:
    parts = decode_header(subj)
    decoded_subj = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded_subj += part.decode(enc or "utf-8", errors="replace")
        else:
            decoded_subj += part

    return decoded_subj


def parse_email_date(date_string: str) -> datetime:
    try:
        split_date = date_string.split("(")[0].strip()
        return datetime.strptime(split_date, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError as e:
        logger.error(e)
