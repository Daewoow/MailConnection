from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from utils.config_utils import *
from utils.imap_utils import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("imap-telegram-forwarder:main")

config: Optional[Config] = None
_worker_task: Optional[asyncio.Task] = None
_worker_stop_event: Optional[asyncio.Event] = None
_lock = asyncio.Lock()

app = FastAPI(title="IMAP to Telegram")
app.mount("/ui", StaticFiles(directory="wwwroot/src", html=True), name="ui")


@app.on_event("startup")
async def startup_event():
    global config, _worker_task, _worker_stop_event
    # cfg = load_config_from_disk()
    if config:
        # config = cfg
        if _worker_task is None:
            _worker_stop_event = asyncio.Event()
            _worker_task = asyncio.create_task(imap_worker_loop(config, _worker_stop_event))
            logger.info("Worker started on startup because config exists.")


@app.on_event("shutdown")
async def shutdown_event():
    await stop_worker()


@app.post("/configure")
async def configure(cfg: Config):
    """
    POST JSON config to configure the connector and start worker.
    Example JSON:
    {
      "imap_host": "imap-mail.outlook.com",
      "imap_port": 993,
      "email_user": "you@outlook.com",
      "email_pass": "your_password-or-app-password",
      "telegram_bot_token": "123456:ABC-DEF...",
      "telegram_chat_id": "123456789",
      "poll_interval": 30
    }
    """
    global config, _worker_task, _worker_stop_event
    async with _lock:
        config = cfg
        # save_config_to_disk(cfg)
        if _worker_task is None or _worker_task.done():
            _worker_stop_event = asyncio.Event()
            _worker_task = asyncio.create_task(imap_worker_loop(config, _worker_stop_event))
            logger.info("Worker started (via /configure).")
    return {"status": "ok", "message": "Configured and worker started."}


@app.post("/start")
async def start_worker_endpoint():
    global config, _worker_task, _worker_stop_event
    if config is None:
        return {"status": "error", "message": "Not configured yet. POST /configure first."}
    async with _lock:
        if _worker_task is None or _worker_task.done():
            _worker_stop_event = asyncio.Event()
            _worker_task = asyncio.create_task(imap_worker_loop(config, _worker_stop_event))
            return {"status": "ok", "message": "Worker started."}
        else:
            return {"status": "ok", "message": "Worker already running."}


@app.post("/stop")
async def stop_worker_endpoint():
    await stop_worker()
    return {"status": "ok", "message": "Worker stop requested."}


async def stop_worker():
    global _worker_task, _worker_stop_event
    async with _lock:
        if _worker_stop_event is not None and not _worker_stop_event.is_set():
            logger.info("Stopping worker")
            _worker_stop_event.set()
        if _worker_task:
            try:
                await asyncio.wait_for(_worker_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Worker did not stop within timeout; cancellation attempted.")
                _worker_task.cancel()
            _worker_task = None
        _worker_stop_event = None


@app.get("/status")
async def status():
    running = _worker_task is not None and not _worker_task.done()
    return {"configured": config is not None, "worker_running": running, "config_file": CONFIG_FILE if config else None}


@app.get("/", status_code=200)
def index():
    return FileResponse("wwwroot/src/index.html")
    # return {"service": "imap-to-telegram-forwarder", "status": "ok", "docs": "/docs"}
