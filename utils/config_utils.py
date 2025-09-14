import json
import logging
import os
from config import Config
from typing import Optional


CONFIG_FILE = "imap_telegram_config.json"
logger = logging.getLogger("imap-telegram-forwarder:utils")

#
# def save_config_to_disk(cfg: Config):
#     with open(CONFIG_FILE, "w", encoding="utf-8") as f:
#         json.dump(cfg.dict(), f, ensure_ascii=False, indent=2)
#     logger.info("Config saved to %s", CONFIG_FILE)
#
#
# def load_config_from_disk() -> Optional[Config]:
#     if not os.path.exists(CONFIG_FILE):
#         return None
#     with open(CONFIG_FILE, encoding="utf-8") as f:
#         data = json.load(f)
#     return Config(**data)
