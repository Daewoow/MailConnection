import re
from email.message import Message
import html


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


def make_telegram_text(msg_obj: Message) -> str:
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
    text = (f"<b>{escape_html(subj)}</b>\n"
            f"From: {escape_html(frm)}\n"
            f"Date: {escape_html(date)}\n"
            f"\n"
            f"{escape_html(preview_text)}")
    return text


def escape_html(s: str) -> str:
    return html.escape(s)
