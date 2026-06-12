import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN
from db.mongo import ensure_indexes

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt= "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("foss")

app = Client(
    name     = "channelfoss_session",
    api_id   = API_ID,
    api_hash = API_HASH,
    bot_token= BOT_TOKEN,
    plugins  = dict(root="plugins"),
)

if __name__ == "__main__":
    log.info("🚀 ChannelFoss Bot starting...")
    try:
        ensure_indexes()
        log.info("✅ MongoDB indexes ensured.")
    except Exception as e:
        log.warning(f"⚠️ MongoDB index error: {e}")
    app.run()
    log.info("🛑 ChannelFoss Bot stopped.")
