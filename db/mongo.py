import dns.resolver
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4"]

from datetime import datetime
from pymongo import MongoClient, ASCENDING
from config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

pairs_col    = db["pairs"]
users_col    = db["users"]
settings_col = db["settings"]

ALL_TYPES = [
    "text", "photo", "video", "audio", "document",
    "animation", "sticker", "voice", "video_note", "poll"
]

def ensure_indexes():
    pairs_col.create_index([("source_id", ASCENDING)], background=True)
    pairs_col.create_index([("active", ASCENDING)],    background=True)
    users_col.create_index([("banned", ASCENDING)],    background=True)
    if not settings_col.find_one({"_id": "global"}):
        settings_col.insert_one({
            "_id": "global",
            "maintenance": False,
            "maintenance_msg": "🔧 Bot sedang dalam maintenance. Silakan coba lagi nanti.",
            "welcome_msg": "👋 Halo {name}!\n\nBot ini memforward pesan dari channel ke channel secara otomatis.",
        })

# ─── Pairs ───────────────────────────────────────────────────────────────────

def add_pair(source_id, source_title, target_id, target_title, mode="copy"):
    doc = {
        "source_id":      source_id,
        "source_title":   source_title,
        "target_id":      target_id,
        "target_title":   target_title,
        "mode":           mode,
        "active":         True,
        "filter_types":   list(ALL_TYPES),
        "caption_prefix": "",
        "caption_suffix": "",
        "blacklist":      [],
        "delay":          0,
        "total_forwarded": 0,
        "created_at":     datetime.utcnow(),
        "last_forward_at": None,
    }
    return str(pairs_col.insert_one(doc).inserted_id)

def get_pair(pair_id):
    from bson import ObjectId
    return pairs_col.find_one({"_id": ObjectId(pair_id)})

def get_all_pairs():
    return list(pairs_col.find().sort("created_at", ASCENDING))

def get_pairs_for_source(source_id):
    return list(pairs_col.find({"source_id": source_id, "active": True}))

def update_pair(pair_id, **kwargs):
    from bson import ObjectId
    pairs_col.update_one({"_id": ObjectId(pair_id)}, {"$set": kwargs})

def delete_pair(pair_id):
    from bson import ObjectId
    pairs_col.delete_one({"_id": ObjectId(pair_id)})

def toggle_pair_active(pair_id):
    from bson import ObjectId
    pair = get_pair(pair_id)
    new_val = not pair["active"]
    pairs_col.update_one({"_id": ObjectId(pair_id)}, {"$set": {"active": new_val}})
    return new_val

def increment_forward_count(pair_id):
    from bson import ObjectId
    pairs_col.update_one(
        {"_id": ObjectId(pair_id)},
        {"$inc": {"total_forwarded": 1},
         "$set": {"last_forward_at": datetime.utcnow()}}
    )

def pair_exists(source_id, target_id):
    return pairs_col.find_one({"source_id": source_id, "target_id": target_id}) is not None

def count_pairs():
    return pairs_col.count_documents({})

def count_active_pairs():
    return pairs_col.count_documents({"active": True})

def total_forwarded_all():
    result = list(pairs_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$total_forwarded"}}}]))
    return result[0]["t"] if result else 0

# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(user_id, first_name="", username=""):
    users_col.update_one(
        {"_id": user_id},
        {
            "$set": {"first_name": first_name, "username": username, "last_seen": datetime.utcnow()},
            "$setOnInsert": {"banned": False, "joined_at": datetime.utcnow()}
        },
        upsert=True
    )

def get_user(user_id):
    return users_col.find_one({"_id": user_id})

def count_users():
    return users_col.count_documents({})

def count_banned():
    return users_col.count_documents({"banned": True})

def ban_user(user_id):
    users_col.update_one({"_id": user_id}, {"$set": {"banned": True}}, upsert=True)

def unban_user(user_id):
    users_col.update_one({"_id": user_id}, {"$set": {"banned": False}})

def get_all_active_user_ids():
    return [u["_id"] for u in users_col.find({"banned": False}, {"_id": 1})]

# ─── Settings ─────────────────────────────────────────────────────────────────

def get_settings():
    return settings_col.find_one({"_id": "global"}) or {}

def update_settings(**kwargs):
    settings_col.update_one({"_id": "global"}, {"$set": kwargs}, upsert=True)

def is_maintenance():
    return get_settings().get("maintenance", False)
