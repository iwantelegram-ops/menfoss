import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import OWNER_ID
from db.mongo import get_all_active_user_ids
from utils.helpers import answer_cb, fmt_num
from utils.keyboards import kb_main, kb_broadcast_menu, kb_bc_confirm

log = logging.getLogger("foss.broadcast")

_bc_waiting: set = set()    # OWNER_ID present → waiting for message
_bc_pending: dict = {}      # OWNER_ID → Message object (ready to send)


def _owner_only_cb(func):
    import functools
    @functools.wraps(func)
    async def wrapper(client, obj, *args, **kwargs):
        uid = getattr(getattr(obj, "from_user", None), "id", 0)
        if uid != OWNER_ID:
            try:
                await obj.answer("🚫 Akses ditolak.", show_alert=True)
            except Exception:
                pass
            return
        return await func(client, obj, *args, **kwargs)
    return wrapper


# ─── Menu ─────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^broadcast_menu$"))
@_owner_only_cb
async def cb_broadcast_menu(client: Client, cb: CallbackQuery):
    answered = False
    try:
        users = len(get_all_active_user_ids())
        text = (
            f"<b>📢 Broadcast</b>\n\n"
            f"Kirim pesan ke semua <code>{users}</code> user aktif.\n\n"
            "Klik tombol di bawah, lalu kirim pesan yang ingin dibroadcast."
        )
        await cb.message.edit_text(text, reply_markup=kb_broadcast_menu(), parse_mode=ParseMode.HTML)
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_broadcast_menu] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# ─── Start: arm waiting state ─────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^bc_start$"))
@_owner_only_cb
async def cb_bc_start(client: Client, cb: CallbackQuery):
    answered = False
    try:
        _bc_pending.pop(OWNER_ID, None)
        _bc_waiting.add(OWNER_ID)
        text = (
            "<b>📢 Broadcast — Kirim Pesan</b>\n\n"
            "Sekarang kirim pesan yang ingin dibroadcast.\n"
            "(Teks, foto, video, atau jenis pesan lainnya)"
        )
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Batal", callback_data="bc_cancel")
        ]]), parse_mode=ParseMode.HTML)
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_bc_start] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# ─── Confirm: send broadcast ──────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^bc_confirm$"))
@_owner_only_cb
async def cb_bc_confirm(client: Client, cb: CallbackQuery):
    answered = False
    try:
        bc_msg = _bc_pending.get(OWNER_ID)
        if not bc_msg:
            await answer_cb(cb, "❌ Tidak ada pesan yang disiapkan.", show_alert=True)
            answered = True
            return

        await answer_cb(cb, "📤 Memulai broadcast...")
        answered = True

        user_ids = get_all_active_user_ids()
        sent = 0
        failed = 0
        for uid in user_ids:
            try:
                await bc_msg.copy(uid)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)

        _bc_pending.pop(OWNER_ID, None)
        await cb.message.edit_text(
            f"<b>✅ Broadcast Selesai!</b>\n\n"
            f"✅ Terkirim : <code>{sent}</code>\n"
            f"❌ Gagal    : <code>{failed}</code>\n"
            f"📊 Total    : <code>{sent + failed}</code>",
            reply_markup=kb_main(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        log.error(f"[cb_bc_confirm] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# ─── Cancel ───────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^bc_cancel$"))
@_owner_only_cb
async def cb_bc_cancel(client: Client, cb: CallbackQuery):
    answered = False
    try:
        _bc_waiting.discard(OWNER_ID)
        _bc_pending.pop(OWNER_ID, None)
        await answer_cb(cb, "❌ Broadcast dibatalkan")
        answered = True
        await cb.message.edit_text(
            "<b>❌ Broadcast dibatalkan.</b>",
            reply_markup=kb_broadcast_menu(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        log.error(f"[cb_bc_cancel] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# ─── Capture broadcast message (group 5) ─────────────────────────────────────

@Client.on_message(filters.private & filters.user(OWNER_ID), group=5)
async def receive_bc_message(client: Client, msg: Message):
    if OWNER_ID not in _bc_waiting:
        return
    if msg.text and msg.text.startswith("/"):
        return

    _bc_waiting.discard(OWNER_ID)
    _bc_pending[OWNER_ID] = msg

    preview_text = msg.text or msg.caption or "[media]"
    await msg.reply(
        f"<b>📢 Preview Broadcast</b>\n\n"
        f"Pesan yang akan dikirim:\n"
        f"<blockquote>{preview_text[:200]}</blockquote>\n\n"
        f"Penerima: <code>{len(get_all_active_user_ids())}</code> user aktif",
        reply_markup=kb_bc_confirm(),
        parse_mode=ParseMode.HTML
    )
