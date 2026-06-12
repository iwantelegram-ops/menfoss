import functools
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import OWNER_ID, BOT_NAME
from db.mongo import (
    ALL_TYPES,
    get_all_pairs, get_pair, add_pair, delete_pair,
    toggle_pair_active, update_pair, pair_exists,
    count_pairs, count_active_pairs, total_forwarded_all,
    count_users, count_banned,
    get_settings, update_settings, is_maintenance,
)
from utils.helpers import answer_cb, fmt_num
from utils.keyboards import (
    kb_main, kb_pairs_list, kb_pair_detail, kb_pair_filters,
    kb_confirm_delete, kb_back_to_detail, kb_back_to_pairs,
    kb_cancel, kb_settings,
)

log = logging.getLogger("foss.owner")

# ─── In-memory state ──────────────────────────────────────────────────────────
_add_pair_state: dict = {}   # uid → {"step": "source"|"target", ...}
_input_state:    dict = {}   # uid → {"action": str, "pair_id": str}


# ─── Decorator ────────────────────────────────────────────────────────────────

def owner_only(func):
    @functools.wraps(func)
    async def wrapper(client, obj, *args, **kwargs):
        uid = getattr(getattr(obj, "from_user", None), "id", 0)
        if uid != OWNER_ID:
            if hasattr(obj, "answer"):
                try:
                    await obj.answer("🚫 Akses ditolak.", show_alert=True)
                except Exception:
                    pass
            return
        return await func(client, obj, *args, **kwargs)
    return wrapper


# ─── Dashboard text ───────────────────────────────────────────────────────────

def dashboard_text() -> str:
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


def pair_detail_text(pair: dict) -> str:
    src      = pair.get("source_title") or str(pair["source_id"])
    tgt      = pair.get("target_title") or str(pair["target_id"])
    mode_str = "📋 Copy" if pair.get("mode") == "copy" else "↗️ Forward"
    status   = "▶️ Aktif" if pair.get("active") else "⏸ Paused"
    types_on = len(pair.get("filter_types", []))
    bl_count = len(pair.get("blacklist", []))
    prefix   = pair.get("caption_prefix") or "—"
    suffix   = pair.get("caption_suffix") or "—"
    delay    = pair.get("delay", 0)
    total    = pair.get("total_forwarded", 0)
    last_fwd = pair.get("last_forward_at")
    last_str = last_fwd.strftime("%d/%m %H:%M") if last_fwd else "belum pernah"
    return (
        f"<b>📡 Pair Detail</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📤 Source  : <b>{src}</b>\n"
        f"   ID      : <code>{pair['source_id']}</code>\n"
        f"📥 Target  : <b>{tgt}</b>\n"
        f"   ID      : <code>{pair['target_id']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Mode    : {mode_str}\n"
        f"📶 Status  : {status}\n"
        f"📨 Forward : <code>{fmt_num(total)}</code>\n"
        f"🕐 Terakhir: <code>{last_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Types   : <code>{types_on}/{len(ALL_TYPES)}</code> aktif\n"
        f"🚫 Blacklist: <code>{bl_count}</code> kata\n"
        f"✏️ Prefix  : <code>{prefix}</code>\n"
        f"✏️ Suffix  : <code>{suffix}</code>\n"
        f"⏱ Delay   : <code>{delay}s</code>\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

# Dashboard
@Client.on_callback_query(filters.regex(r"^dashboard$"))
@owner_only
async def cb_dashboard(client: Client, cb: CallbackQuery):
    answered = False
    try:
        await cb.message.edit_text(dashboard_text(), reply_markup=kb_main(), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_dashboard] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Pairs list
@Client.on_callback_query(filters.regex(r"^pairs_list$"))
@owner_only
async def cb_pairs_list(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pairs = get_all_pairs()
        text  = (
            f"<b>📡 Daftar Channel Pairs ({len(pairs)})</b>\n\n"
            + ("Pilih pair untuk mengelola:" if pairs else "Belum ada pair. Tambahkan sekarang!")
        )
        await cb.message.edit_text(text, reply_markup=kb_pairs_list(pairs), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pairs_list] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Pair detail
@Client.on_callback_query(filters.regex(r"^pair_detail:(.+)$"))
@owner_only
async def cb_pair_detail(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        pair = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌ Pair tidak ditemukan.", show_alert=True)
            answered = True
            return
        await cb.message.edit_text(pair_detail_text(pair), reply_markup=kb_pair_detail(pair), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_detail] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Toggle active
@Client.on_callback_query(filters.regex(r"^pair_toggle:(.+)$"))
@owner_only
async def cb_pair_toggle(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid     = cb.matches[0].group(1)
        new_val = toggle_pair_active(pid)
        status  = "▶️ Aktif" if new_val else "⏸ Paused"
        await answer_cb(cb, f"Status: {status}")
        answered = True
        pair = get_pair(pid)
        if pair:
            await cb.message.edit_text(pair_detail_text(pair), reply_markup=kb_pair_detail(pair), parse_mode="html")
    except Exception as e:
        log.error(f"[cb_pair_toggle] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Change mode (copy ↔ forward)
@Client.on_callback_query(filters.regex(r"^pair_mode:(.+):(copy|forward)$"))
@owner_only
async def cb_pair_mode(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        mode = cb.matches[0].group(2)
        update_pair(pid, mode=mode)
        lbl = "📋 Copy" if mode == "copy" else "↗️ Forward"
        await answer_cb(cb, f"Mode: {lbl}")
        answered = True
        pair = get_pair(pid)
        if pair:
            await cb.message.edit_text(pair_detail_text(pair), reply_markup=kb_pair_detail(pair), parse_mode="html")
    except Exception as e:
        log.error(f"[cb_pair_mode] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Filter types menu
@Client.on_callback_query(filters.regex(r"^pair_filters:(.+)$"))
@owner_only
async def cb_pair_filters(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        pair = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌ Pair tidak ditemukan.", show_alert=True)
            answered = True
            return
        active_count = len(pair.get("filter_types", []))
        text = (
            f"<b>🔍 Filter Tipe Pesan</b>\n"
            f"Tap untuk toggle aktif/nonaktif.\n"
            f"Aktif: <code>{active_count}/{len(ALL_TYPES)}</code>"
        )
        await cb.message.edit_text(text, reply_markup=kb_pair_filters(pair), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_filters] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Toggle individual filter type
@Client.on_callback_query(filters.regex(r"^pair_filter_toggle:(.+):(\w+)$"))
@owner_only
async def cb_pair_filter_toggle(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid   = cb.matches[0].group(1)
        ftype = cb.matches[0].group(2)
        pair  = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌", show_alert=True)
            answered = True
            return
        types = list(pair.get("filter_types", []))
        if ftype in types:
            types.remove(ftype)
            msg_txt = f"☐ {ftype} off"
        else:
            types.append(ftype)
            msg_txt = f"✅ {ftype} on"
        update_pair(pid, filter_types=types)
        await answer_cb(cb, msg_txt)
        answered = True
        pair = get_pair(pid)
        await cb.message.edit_reply_markup(kb_pair_filters(pair))
    except Exception as e:
        log.error(f"[cb_pair_filter_toggle] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Caption input
@Client.on_callback_query(filters.regex(r"^pair_caption:(.+)$"))
@owner_only
async def cb_pair_caption(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        pair = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌", show_alert=True)
            answered = True
            return
        _input_state[OWNER_ID] = {"action": "caption", "pair_id": pid}
        text = (
            f"<b>✏️ Edit Caption Prefix / Suffix</b>\n\n"
            f"Caption sekarang:\n"
            f"  Prefix: <code>{pair.get('caption_prefix') or '—'}</code>\n"
            f"  Suffix: <code>{pair.get('caption_suffix') or '—'}</code>\n\n"
            f"Format kirim:\n"
            f"<code>PREFIX|||SUFFIX</code>\n\n"
            f"Contoh: <code>📢 Update terbaru|||#berita</code>\n"
            f"Kirim <code>-</code> untuk hapus keduanya."
        )
        await cb.message.edit_text(text, reply_markup=kb_cancel("caption", pid), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_caption] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Blacklist input
@Client.on_callback_query(filters.regex(r"^pair_blacklist:(.+)$"))
@owner_only
async def cb_pair_blacklist(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        pair = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌", show_alert=True)
            answered = True
            return
        bl     = pair.get("blacklist", [])
        bl_str = ", ".join(bl) if bl else "—"
        _input_state[OWNER_ID] = {"action": "blacklist", "pair_id": pid}
        text = (
            f"<b>🚫 Keyword Blacklist</b>\n\n"
            f"Kata yang diblokir sekarang:\n<code>{bl_str}</code>\n\n"
            f"Kirim kata-kata baru dipisah koma:\n"
            f"Contoh: <code>spam, iklan, judi</code>\n"
            f"Kirim <code>-</code> untuk kosongkan blacklist."
        )
        await cb.message.edit_text(text, reply_markup=kb_cancel("blacklist", pid), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_blacklist] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Delay input
@Client.on_callback_query(filters.regex(r"^pair_delay:(.+)$"))
@owner_only
async def cb_pair_delay(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        pair = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌", show_alert=True)
            answered = True
            return
        _input_state[OWNER_ID] = {"action": "delay", "pair_id": pid}
        text = (
            f"<b>⏱ Atur Delay Forward</b>\n\n"
            f"Delay sekarang: <code>{pair.get('delay', 0)} detik</code>\n\n"
            f"Kirim angka detik (0 = tanpa delay):\n"
            f"Contoh: <code>5</code>"
        )
        await cb.message.edit_text(text, reply_markup=kb_cancel("delay", pid), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_delay] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Remove confirm
@Client.on_callback_query(filters.regex(r"^pair_remove_confirm:(.+)$"))
@owner_only
async def cb_pair_remove_confirm(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid  = cb.matches[0].group(1)
        pair = get_pair(pid)
        if not pair:
            await answer_cb(cb, "❌", show_alert=True)
            answered = True
            return
        src = pair.get("source_title") or str(pair["source_id"])
        tgt = pair.get("target_title") or str(pair["target_id"])
        text = (
            f"⚠️ <b>Konfirmasi Hapus Pair</b>\n\n"
            f"Yakin hapus:\n<b>{src} → {tgt}</b>?\n\n"
            f"Tindakan ini tidak dapat dibatalkan!"
        )
        await cb.message.edit_text(text, reply_markup=kb_confirm_delete(pid), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_remove_confirm] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Remove execute
@Client.on_callback_query(filters.regex(r"^pair_remove_do:(.+)$"))
@owner_only
async def cb_pair_remove_do(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid = cb.matches[0].group(1)
        delete_pair(pid)
        await answer_cb(cb, "✅ Pair dihapus!")
        answered = True
        pairs = get_all_pairs()
        text  = f"<b>📡 Daftar Channel Pairs ({len(pairs)})</b>"
        await cb.message.edit_text(text, reply_markup=kb_pairs_list(pairs), parse_mode="html")
    except Exception as e:
        log.error(f"[cb_pair_remove_do] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Add pair — step 1
@Client.on_callback_query(filters.regex(r"^pair_add$"))
@owner_only
async def cb_pair_add(client: Client, cb: CallbackQuery):
    answered = False
    try:
        _add_pair_state[OWNER_ID] = {"step": "source"}
        text = (
            "<b>➕ Tambah Channel Pair</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>Langkah 1/2 — Source Channel</b>\n\n"
            "Kirim ID numerik atau username channel sumber:\n"
            "Contoh: <code>-1001234567890</code>  atau  <code>@channelku</code>\n\n"
            "<i>⚠️ Bot harus sudah menjadi admin di channel tersebut.</i>"
        )
        await cb.message.edit_text(text, reply_markup=kb_cancel("add_pair"), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_pair_add] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Cancel any text input
@Client.on_callback_query(filters.regex(r"^cancel_input:(.+):(.*)$"))
@owner_only
async def cb_cancel_input(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pid = cb.matches[0].group(2)
        _add_pair_state.pop(OWNER_ID, None)
        _input_state.pop(OWNER_ID, None)

        if pid:
            pair = get_pair(pid)
            if pair:
                await answer_cb(cb, "❌ Dibatalkan")
                answered = True
                await cb.message.edit_text(
                    pair_detail_text(pair),
                    reply_markup=kb_pair_detail(pair),
                    parse_mode="html"
                )
                return

        pairs = get_all_pairs()
        await answer_cb(cb, "❌ Dibatalkan")
        answered = True
        await cb.message.edit_text(
            f"<b>📡 Daftar Channel Pairs ({len(pairs)})</b>",
            reply_markup=kb_pairs_list(pairs),
            parse_mode="html"
        )
    except Exception as e:
        log.error(f"[cb_cancel_input] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Settings menu
@Client.on_callback_query(filters.regex(r"^settings_menu$"))
@owner_only
async def cb_settings_menu(client: Client, cb: CallbackQuery):
    answered = False
    try:
        s = get_settings()
        text = (
            "<b>⚙️ Pengaturan Bot</b>\n\n"
            f"<b>Welcome:</b>\n<code>{(s.get('welcome_msg') or '—')[:100]}</code>\n\n"
            f"<b>Maintenance:</b>\n<code>{(s.get('maintenance_msg') or '—')[:100]}</code>"
        )
        await cb.message.edit_text(text, reply_markup=kb_settings(), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_settings_menu] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


@Client.on_callback_query(filters.regex(r"^edit_welcome$"))
@owner_only
async def cb_edit_welcome(client: Client, cb: CallbackQuery):
    answered = False
    try:
        _input_state[OWNER_ID] = {"action": "edit_welcome", "pair_id": ""}
        text = (
            "<b>✏️ Edit Pesan Welcome</b>\n\n"
            "Variabel tersedia:\n"
            "• <code>{name}</code> — nama depan user\n"
            "• <code>{bot}</code> — nama bot\n\n"
            "Kirim teks baru:"
        )
        await cb.message.edit_text(text, reply_markup=kb_cancel("edit_welcome"), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_edit_welcome] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


@Client.on_callback_query(filters.regex(r"^edit_maintenance_msg$"))
@owner_only
async def cb_edit_maintenance_msg(client: Client, cb: CallbackQuery):
    answered = False
    try:
        _input_state[OWNER_ID] = {"action": "edit_maintenance_msg", "pair_id": ""}
        text = "<b>✏️ Edit Pesan Maintenance</b>\n\nKirim teks baru:"
        await cb.message.edit_text(text, reply_markup=kb_cancel("edit_maintenance_msg"), parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_edit_maintenance_msg] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Maintenance toggle
@Client.on_callback_query(filters.regex(r"^toggle_maintenance$"))
@owner_only
async def cb_toggle_maintenance(client: Client, cb: CallbackQuery):
    answered = False
    try:
        s       = get_settings()
        new_val = not s.get("maintenance", False)
        update_settings(maintenance=new_val)
        status  = "🔴 ON" if new_val else "🟢 OFF"
        await answer_cb(cb, f"Maintenance: {status}")
        answered = True
        await cb.message.edit_text(dashboard_text(), reply_markup=kb_main(), parse_mode="html")
    except Exception as e:
        log.error(f"[cb_toggle_maintenance] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# Statistics
@Client.on_callback_query(filters.regex(r"^stats_global$"))
@owner_only
async def cb_stats_global(client: Client, cb: CallbackQuery):
    answered = False
    try:
        pairs = get_all_pairs()
        if not pairs:
            text = "📊 Belum ada data statistik."
        else:
            lines = ["<b>📊 Statistik Per Pair</b>\n"]
            for i, p in enumerate(pairs, 1):
                src   = (p.get("source_title") or str(p["source_id"]))[:22]
                tgt   = (p.get("target_title") or str(p["target_id"]))[:22]
                total = p.get("total_forwarded", 0)
                icon  = "▶️" if p.get("active") else "⏸"
                lines.append(f"{i}. {icon} {src} → {tgt}\n   📨 <code>{fmt_num(total)}</code>")
            total_all = sum(p.get("total_forwarded", 0) for p in pairs)
            lines.append(f"\n<b>📨 Total Semua: <code>{fmt_num(total_all)}</code></b>")
            text = "\n".join(lines)

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Menu Utama", callback_data="dashboard")
        ]])
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="html")
        answered = True
        await answer_cb(cb)
    except Exception as e:
        log.error(f"[cb_stats_global] {e}")
    finally:
        if not answered:
            await answer_cb(cb)


# ─────────────────────────────────────────────────────────────────────────────
#  TEXT INPUT HANDLER (group=3)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(
    filters.text & filters.private & ~filters.regex(r"^/"),
    group=3
)
@owner_only
async def handle_owner_text(client: Client, msg: Message):
    uid  = msg.from_user.id
    text = msg.text.strip()

    # ── Add pair flow ────────────────────────────────────────────────────────
    if uid in _add_pair_state:
        state = _add_pair_state[uid]
        if state["step"] == "source":
            await _add_pair_source(client, msg, text)
        elif state["step"] == "target":
            await _add_pair_target(client, msg, text, state)
        return

    # ── General input state ──────────────────────────────────────────────────
    if uid in _input_state:
        state  = _input_state.pop(uid)
        action = state.get("action", "")
        pid    = state.get("pair_id", "")
        await _handle_input(msg, action, pid, text)
        return


async def _add_pair_source(client: Client, msg: Message, text: str):
    try:
        chat = await client.get_chat(text)
    except Exception as e:
        await msg.reply(f"❌ Gagal resolve channel: <code>{e}</code>\n\nCoba lagi:", parse_mode="html")
        return

    if chat.type.value not in ("channel", "supergroup"):
        await msg.reply("❌ Harus berupa channel atau supergroup. Coba lagi:")
        return

    _add_pair_state[OWNER_ID]["step"]         = "target"
    _add_pair_state[OWNER_ID]["source_id"]    = chat.id
    _add_pair_state[OWNER_ID]["source_title"] = chat.title or str(chat.id)

    await msg.reply(
        f"✅ Source: <b>{chat.title}</b>  (<code>{chat.id}</code>)\n\n"
        "<b>Langkah 2/2 — Target Channel</b>\n\n"
        "Kirim ID atau username channel tujuan:",
        reply_markup=kb_cancel("add_pair"),
        parse_mode="html"
    )


async def _add_pair_target(client: Client, msg: Message, text: str, state: dict):
    try:
        chat = await client.get_chat(text)
    except Exception as e:
        await msg.reply(f"❌ Gagal resolve channel: <code>{e}</code>\n\nCoba lagi:", parse_mode="html")
        return

    if chat.type.value not in ("channel", "supergroup"):
        await msg.reply("❌ Harus berupa channel atau supergroup. Coba lagi:")
        return

    if state["source_id"] == chat.id:
        await msg.reply("❌ Source dan target tidak boleh channel yang sama!")
        return

    if pair_exists(state["source_id"], chat.id):
        await msg.reply("⚠️ Pair ini sudah ada!", reply_markup=kb_back_to_pairs())
        _add_pair_state.pop(OWNER_ID, None)
        return

    add_pair(
        source_id    = state["source_id"],
        source_title = state["source_title"],
        target_id    = chat.id,
        target_title = chat.title or str(chat.id),
    )
    _add_pair_state.pop(OWNER_ID, None)

    pairs = get_all_pairs()
    await msg.reply(
        f"<b>✅ Pair berhasil ditambahkan!</b>\n\n"
        f"📤 <b>{state['source_title']}</b>\n"
        f"   ↓  (copy mode, semua tipe aktif)\n"
        f"📥 <b>{chat.title}</b>",
        reply_markup=kb_pairs_list(pairs),
        parse_mode="html"
    )


async def _handle_input(msg: Message, action: str, pid: str, text: str):
    if action == "caption":
        if text == "-":
            update_pair(pid, caption_prefix="", caption_suffix="")
            await msg.reply("✅ Caption prefix/suffix dihapus.", reply_markup=kb_back_to_detail(pid))
        else:
            parts  = text.split("|||", 1)
            prefix = parts[0].strip()
            suffix = parts[1].strip() if len(parts) > 1 else ""
            update_pair(pid, caption_prefix=prefix, caption_suffix=suffix)
            await msg.reply(
                f"✅ Caption diperbarui.\n"
                f"Prefix: <code>{prefix or '—'}</code>\n"
                f"Suffix: <code>{suffix or '—'}</code>",
                reply_markup=kb_back_to_detail(pid),
                parse_mode="html"
            )

    elif action == "blacklist":
        if text == "-":
            update_pair(pid, blacklist=[])
            await msg.reply("✅ Blacklist dikosongkan.", reply_markup=kb_back_to_detail(pid))
        else:
            words = [w.strip() for w in text.split(",") if w.strip()]
            update_pair(pid, blacklist=words)
            await msg.reply(
                f"✅ Blacklist diperbarui ({len(words)} kata):\n"
                f"<code>{', '.join(words)}</code>",
                reply_markup=kb_back_to_detail(pid),
                parse_mode="html"
            )

    elif action == "delay":
        try:
            delay = max(0, int(text))
            update_pair(pid, delay=delay)
            await msg.reply(
                f"✅ Delay diatur: <code>{delay} detik</code>",
                reply_markup=kb_back_to_detail(pid),
                parse_mode="html"
            )
        except ValueError:
            await msg.reply("❌ Masukkan angka yang valid (contoh: 5)", reply_markup=kb_back_to_detail(pid))

    elif action == "edit_welcome":
        update_settings(welcome_msg=text)
        await msg.reply(
            f"✅ Pesan welcome diperbarui:\n<code>{text[:200]}</code>",
            reply_markup=kb_main(),
            parse_mode="html"
        )

    elif action == "edit_maintenance_msg":
        update_settings(maintenance_msg=text)
        await msg.reply(
            f"✅ Pesan maintenance diperbarui:\n<code>{text[:200]}</code>",
            reply_markup=kb_main(),
            parse_mode="html"
        )
