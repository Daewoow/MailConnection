import asyncio
import imaplib
import email
import httpx
import logging
import traceback
from config import Config
from .parsing_utils import make_telegram_text


logger = logging.getLogger("imap-telegram-forwarder:imap")


async def imap_worker_loop(cfg: Config, stop_event: asyncio.Event):
    logger.info("Starting IMAP worker (poll interval %s sec)...", cfg.poll_interval)
    async with httpx.AsyncClient(timeout=30) as http_client:
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(process_unseen_and_forward, cfg, http_client)
            except Exception as e:
                logger.exception("Error in IMAP processing loop: %s", e)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=cfg.poll_interval)
            except asyncio.TimeoutError:
                continue
    logger.info("IMAP worker stopped.")


def process_unseen_and_forward(cfg: Config, http_client: httpx.AsyncClient):
    """
    Функция блокировки, выполняемая в потоке: подключается к IMAP, находит непросмотренные(!) сообщения,
    пересылает их в Telegram и помечает как просмотренные.
    """
    logger.debug("Connecting to IMAP %s:%s as %s", cfg.imap_host, cfg.imap_port, cfg.email_user)
    m = imaplib.IMAP4_SSL(host=cfg.imap_host, port=cfg.imap_port)
    try:
        m.login(cfg.email_user, cfg.email_pass)
    except imaplib.IMAP4.error as e:
        logger.error("IMAP login failed: %s", traceback.format_exc())
        m.logout()
        return
    try:
        m.select()
        typ, data = m.search(None, "UNSEEN")
        if typ != "OK":
            logger.warning("IMAP search failed: %s %s", typ, data)
            return
        uids = data[0].split()
        if not uids:
            logger.debug("No new messages.")
            return
        logger.info("Found %d unseen messages", len(uids))
        for uid in uids:
            try:
                typ, msg_data = m.fetch(uid, '(RFC822)')
                if typ != "OK":
                    logger.warning("Failed to fetch UID %s: %s %s", uid, typ, msg_data)
                    continue
                raw = _extract_raw_from_fetch(msg_data)
                msg_obj = email.message_from_bytes(raw)
                text = make_telegram_text(msg_obj)
                # Асинхронный клиент нельзя использовать в отдельном потоке, поэтому используем синхронный клиент
                send_telegram_sync(cfg.telegram_bot_token, cfg.telegram_chat_id, text)
                m.store(uid, '+FLAGS', '\\Seen')
                logger.info("Forwarded UID %s to Telegram and marked as Seen",
                            uid.decode() if isinstance(uid, bytes) else uid)
            except Exception as e:
                logger.exception("Error handling UID %s: %s", uid, e)
    finally:
        try:
            m.close()
        except Exception:
            pass
        m.logout()


def send_telegram_sync(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    with httpx.Client(timeout=20) as client:
        r = client.post(url, data=payload)
        if r.status_code != 200:
            logger.error("Telegram send failed: %s %s", r.status_code, r.text)
        else:
            logger.debug("Telegram message sent.")


def _extract_raw_from_fetch(msg_data) -> bytes | None:
    if not msg_data:
        return None
    for part in msg_data:
        if isinstance(part, tuple) and len(part) >= 2 and part[1]:
            return part[1]
        if isinstance(part, bytes):
            return part
    return None
