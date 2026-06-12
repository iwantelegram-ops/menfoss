import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID, BOT_NAME
from db.mongo import upsert_user, get_settings, is_maintenance, count_pairs, count_active_pairs, total_forwarded_all, count_users
from utils.helpers import fmt_num
from utils.keyboards import kb_main

log = logging.getLogger("foss.start")


def _dashboard_text() -> str:
    from db.mongo import count_banned
    pairs  = count_pairs()
    active = count_active_pairs()
    s      = get_settings()
    maint  = "🔴 ON" if s.get("maintenance") else "🟢 OFF"
    return (
        f"<b>🤖 {BOT_NAME} — Dashboard</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📡 <b>Channel Pairs</b>\n"
        f"  ▶️ Aktif  : <code>{active}</code>\n"
        f"  ⏸ Paused : <code>{pairs - active}</code>\n"
        f"  📊 Total  : <code>{pairs}</code>\n\n"
        f"📨 <b>Total Forward</b>: <code>{fmt_num(total_forwarded_all())}</code>\n\n"
        f"👥 <b>Users</b>: <code>{count_users()}</code>  "
        f"(🚫 Banned: <code>{count_banned()}</code>)\n\n"
        f"🔧 <b>Maintenance</b>: {maint}"
    )


@Client.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, msg: Message):
    user = msg.from_user
    upsert_user(user.id, user.first_name or "", user.username or "")

    if user.id == OWNER_ID:
        await msg.reply(_dashboard_text(), reply_markup=kb_main(), parse_mode="html")
        return

    if is_maintenance():
        s = get_settings()
        await msg.reply(s.get("maintenance_msg", "🔧 Bot sedang maintenance."))
        return

    s = get_settings()
    welcome = s.get("welcome_msg", f"👋 Halo {{name}}!\n\nSelamat datang di <b>{BOT_NAME}</b>.")
    await msg.reply(
        welcome.replace("{name}", user.first_name or "").replace("{bot}", BOT_NAME),
        parse_mode="html"
    )


@Client.on_message(filters.command(["help", "h"]) & filters.private)
async def cmd_help(client: Client, msg: Message):
    await msg.reply(
        f"<b>ℹ️ {BOT_NAME} Help</b>\n\n"
        "Bot ini memforward pesan dari channel sumber ke channel tujuan secara otomatis.\n\n"
        "<b>Commands:</b>\n"
        "/start — Panel utama (owner) / Sambutan (user)\n"
        "/status — Lihat status bot\n"
        "/cancel — Batalkan input yang sedang berlangsung\n"
        "/help — Bantuan ini\n",
        parse_mode="html"
    )


@Client.on_message(filters.command("status") & filters.private)
async def cmd_status(client: Client, msg: Message):
    await msg.reply(
        f"<b>📊 Status {BOT_NAME}</b>\n\n"
        f"📡 Pairs  : <code>{count_pairs()}</code>  (▶️ aktif: <code>{count_active_pairs()}</code>)\n"
        f"📨 Forward: <code>{fmt_num(total_forwarded_all())}</code> pesan\n"
        f"👥 Users  : <code>{count_users()}</code>\n"
        f"🔧 Maint  : {'🔴 ON' if is_maintenance() else '🟢 OFF'}\n",
        parse_mode="html"
    )


@Client.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, msg: Message):
    if msg.from_user.id != OWNER_ID:
        return
    from plugins.owner import _add_pair_state, _input_state
    from plugins.broadcast import _bc_waiting, _bc_pending
    cleared = any([
        _add_pair_state.pop(OWNER_ID, None),
        _input_state.pop(OWNER_ID, None),
        _bc_waiting.discard(OWNER_ID) or OWNER_ID in _bc_waiting,
        _bc_pending.pop(OWNER_ID, None),
    ])
    await msg.reply(
        "✅ Semua input dibatalkan." if cleared else "ℹ️ Tidak ada input yang aktif.",
        reply_markup=kb_main()
    )
