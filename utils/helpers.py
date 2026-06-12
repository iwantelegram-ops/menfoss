import logging
from pyrogram.types import Message

log = logging.getLogger("foss.helpers")


async def answer_cb(cb, text: str = "✅", show_alert: bool = False):
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass


def fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def get_msg_type(msg: Message) -> str | None:
    if msg.photo:       return "photo"
    if msg.video:       return "video"
    if msg.audio:       return "audio"
    if msg.document:    return "document"
    if msg.animation:   return "animation"
    if msg.sticker:     return "sticker"
    if msg.voice:       return "voice"
    if msg.video_note:  return "video_note"
    if msg.poll:        return "poll"
    if msg.text:        return "text"
    return None
