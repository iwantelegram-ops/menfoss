from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ─── Main dashboard ───────────────────────────────────────────────────────────

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Kelola Pairs",  callback_data="pairs_list"),
         InlineKeyboardButton("📊 Statistik",     callback_data="stats_global")],
        [InlineKeyboardButton("📢 Broadcast",     callback_data="broadcast_menu"),
         InlineKeyboardButton("⚙️ Pengaturan",   callback_data="settings_menu")],
        [InlineKeyboardButton("🔧 Maintenance",   callback_data="toggle_maintenance"),
         InlineKeyboardButton("🔄 Refresh",       callback_data="dashboard")],
    ])


# ─── Pairs list ───────────────────────────────────────────────────────────────

def kb_pairs_list(pairs):
    rows = []
    for p in pairs:
        icon = "▶️" if p["active"] else "⏸"
        src  = (p.get("source_title") or str(p["source_id"]))[:18]
        tgt  = (p.get("target_title") or str(p["target_id"]))[:18]
        pid  = str(p["_id"])
        count = fmt_short(p.get("total_forwarded", 0))
        rows.append([InlineKeyboardButton(
            f"{icon} {src} → {tgt}  [{count}]",
            callback_data=f"pair_detail:{pid}"
        )])
    rows.append([InlineKeyboardButton("➕ Tambah Pair", callback_data="pair_add")])
    rows.append([InlineKeyboardButton("🏠 Menu Utama",  callback_data="dashboard")])
    return InlineKeyboardMarkup(rows)


def fmt_short(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


# ─── Pair detail ──────────────────────────────────────────────────────────────

def kb_pair_detail(pair):
    pid    = str(pair["_id"])
    active = pair.get("active", True)
    mode   = pair.get("mode", "copy")
    delay  = pair.get("delay", 0)

    toggle_lbl = "⏸ Jeda"     if active else "▶️ Aktifkan"
    mode_lbl   = "📋 Copy"    if mode == "copy" else "↗️ Forward"
    mode_next  = "forward"    if mode == "copy" else "copy"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_lbl,               callback_data=f"pair_toggle:{pid}"),
         InlineKeyboardButton(mode_lbl,                 callback_data=f"pair_mode:{pid}:{mode_next}")],
        [InlineKeyboardButton("🔍 Filter Tipe",         callback_data=f"pair_filters:{pid}"),
         InlineKeyboardButton("✏️ Caption",             callback_data=f"pair_caption:{pid}")],
        [InlineKeyboardButton("🚫 Blacklist",            callback_data=f"pair_blacklist:{pid}"),
         InlineKeyboardButton(f"⏱ Delay: {delay}s",    callback_data=f"pair_delay:{pid}")],
        [InlineKeyboardButton("❌ Hapus Pair",           callback_data=f"pair_remove_confirm:{pid}")],
        [InlineKeyboardButton("🔙 Daftar Pairs",        callback_data="pairs_list")],
    ])


# ─── Filter types ─────────────────────────────────────────────────────────────

TYPE_EMOJI = {
    "text": "📝", "photo": "🖼", "video": "🎬", "audio": "🎵",
    "document": "📄", "animation": "🎞", "sticker": "🎭",
    "voice": "🎤", "video_note": "📹", "poll": "📊",
}


def kb_pair_filters(pair):
    from db.mongo import ALL_TYPES
    pid         = str(pair["_id"])
    active_set  = set(pair.get("filter_types", ALL_TYPES))
    rows = []
    row  = []
    for i, t in enumerate(ALL_TYPES):
        check = "✅" if t in active_set else "☐"
        emoji = TYPE_EMOJI.get(t, "")
        row.append(InlineKeyboardButton(
            f"{check}{emoji}{t}",
            callback_data=f"pair_filter_toggle:{pid}:{t}"
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"pair_detail:{pid}")])
    return InlineKeyboardMarkup(rows)


# ─── Misc ─────────────────────────────────────────────────────────────────────

def kb_confirm_delete(pid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ya, Hapus!",  callback_data=f"pair_remove_do:{pid}"),
        InlineKeyboardButton("❌ Batal",        callback_data=f"pair_detail:{pid}"),
    ]])


def kb_back_to_detail(pid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Kembali ke Pair", callback_data=f"pair_detail:{pid}")
    ]])


def kb_back_to_pairs():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Daftar Pairs", callback_data="pairs_list")
    ]])


def kb_cancel(action: str = "cancel", pid: str = ""):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Batal", callback_data=f"cancel_input:{action}:{pid}")
    ]])


def kb_settings():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Pesan Welcome",      callback_data="edit_welcome")],
        [InlineKeyboardButton("📋 Edit Pesan Maintenance",  callback_data="edit_maintenance_msg")],
        [InlineKeyboardButton("🏠 Menu Utama",              callback_data="dashboard")],
    ])


def kb_broadcast_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Kirim Broadcast", callback_data="bc_start")],
        [InlineKeyboardButton("🏠 Menu Utama",       callback_data="dashboard")],
    ])


def kb_bc_confirm():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Kirim Sekarang", callback_data="bc_confirm"),
        InlineKeyboardButton("❌ Batal",           callback_data="bc_cancel"),
    ]])
