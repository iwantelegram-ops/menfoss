import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from db.mongo import get_pairs_for_source, increment_forward_count
from utils.helpers import get_msg_type

log = logging.getLogger("foss.forwarder")


@Client.on_message(filters.channel, group=-2)
async def on_channel_post(client: Client, msg: Message):
    source_id = msg.chat.id
    pairs = get_pairs_for_source(source_id)
    if not pairs:
        return
    for pair in pairs:
        asyncio.create_task(_forward_one(client, msg, pair))


async def _forward_one(client: Client, msg: Message, pair: dict):
    pid = str(pair["_id"])
    try:
        # ── Type filter ──────────────────────────────────────────
        msg_type = get_msg_type(msg)
        if msg_type and msg_type not in pair.get("filter_types", []):
            log.debug(f"[{pid}] skip: type '{msg_type}' not in filter_types")
            return

        # ── Blacklist ────────────────────────────────────────────
        text_content = msg.text or msg.caption or ""
        blacklist    = pair.get("blacklist", [])
        if any(kw.lower() in text_content.lower() for kw in blacklist if kw.strip()):
            log.debug(f"[{pid}] skip: blacklisted keyword found")
            return

        # ── Delay ────────────────────────────────────────────────
        delay = pair.get("delay", 0)
        if delay > 0:
            await asyncio.sleep(delay)

        target_id = pair["target_id"]
        mode      = pair.get("mode", "copy")

        if mode == "forward":
            await client.forward_messages(target_id, msg.chat.id, msg.id)
        else:
            # ── Build caption ──────────────────────────────────
            prefix = (pair.get("caption_prefix") or "").strip()
            suffix = (pair.get("caption_suffix") or "").strip()

            if prefix or suffix:
                orig    = (msg.caption or msg.text or "").strip()
                parts   = [p for p in [prefix, orig, suffix] if p]
                new_cap = "\n".join(parts)
            else:
                new_cap = None  # preserve original

            await client.copy_message(
                chat_id      = target_id,
                from_chat_id = msg.chat.id,
                message_id   = msg.id,
                caption      = new_cap,
            )

        increment_forward_count(pid)
        log.info(f"[{pid}] ✅ {msg.chat.id} → {target_id}  msg_id={msg.id}")

    except Exception as e:
        log.error(f"[{pid}] ❌ forward error: {e}")
