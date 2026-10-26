import aiosqlite
import asyncio
import os
import time
from pathlib import Path
import config

INIT_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA temp_store=MEMORY;
PRAGMA cache_size=-16000;

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    channel_id TEXT UNIQUE,
    guild_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL,
    closed_at INTEGER,
    claimed_by TEXT,
    close_reason TEXT,
    transcript_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_tickets_user_status ON tickets(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    author_id TEXT NOT NULL,
    author_name TEXT,
    content TEXT,
    is_bot INTEGER DEFAULT 0,
    attachments TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON ticket_messages(ticket_id, created_at);

CREATE TABLE IF NOT EXISTS ticket_bans (
    user_id TEXT PRIMARY KEY,
    reason TEXT,
    banned_at INTEGER,
    banned_by TEXT
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id TEXT PRIMARY KEY,
    category_id TEXT,
    staff_role_id TEXT,
    log_channel_id TEXT,
    announce_channel_id TEXT,
    welcome_message TEXT
);

CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);
"""

class Database:
    def __init__(self, path: str = config.DB_PATH):
        self.path = path
        self._lock = asyncio.Lock()

    async def init(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        Path(config.TRANSCRIPT_DIR).mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(INIT_SQL)
            await db.commit()
            # upsert guild config par défaut
            await db.execute("""
                INSERT OR IGNORE INTO guild_config (guild_id, category_id, staff_role_id, log_channel_id, announce_channel_id)
                VALUES (?, ?, ?, ?, ?)
            """, (str(config.GUILD_ID), str(config.TICKET_CATEGORY_ID), str(config.STAFF_ROLE_ID),
                  str(config.LOG_CHANNEL_ID) if config.LOG_CHANNEL_ID else None,
                  str(config.ANNOUNCE_CHANNEL_ID) if config.ANNOUNCE_CHANNEL_ID else None))
            await db.commit()

    async def get_guild_config(self, guild_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (str(guild_id),)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def update_guild_config(self, guild_id: int, **kwargs):
        allowed = {"category_id", "staff_role_id", "log_channel_id", "announce_channel_id", "welcome_message"}
        updates = {k: str(v) for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return
        set_clause = ", ".join([f"{k}=?" for k in updates])
        vals = list(updates.values()) + [str(guild_id)]
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE guild_config SET {set_clause} WHERE guild_id = ?", vals)
            await db.commit()

    # --- Tickets ---

    async def create_ticket(self, user_id: int, channel_id: int, guild_id: int) -> int:
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO tickets (user_id, channel_id, guild_id, status, created_at) VALUES (?, ?, ?, 'open', ?)",
                (str(user_id), str(channel_id), str(guild_id), now)
            )
            await db.commit()
            return cur.lastrowid

    async def get_open_ticket_by_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tickets WHERE user_id = ? AND status = 'open' LIMIT 1", (str(user_id),)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_ticket_by_channel(self, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tickets WHERE channel_id = ?", (str(channel_id),)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_ticket_by_channel_or_user(self, channel_id: int = None, user_id: int = None):
        if channel_id:
            t = await self.get_ticket_by_channel(channel_id)
            if t:
                return t
        if user_id:
            return await self.get_open_ticket_by_user(user_id)
        return None

    async def close_ticket(self, channel_id: int, reason: str = None):
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE tickets SET status='closed', closed_at=?, close_reason=? WHERE channel_id=?",
                (now, reason, str(channel_id))
            )
            await db.commit()

    async def set_transcript_path(self, channel_id: int, path: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE tickets SET transcript_path=? WHERE channel_id=?", (path, str(channel_id)))
            await db.commit()

    async def claim_ticket(self, channel_id: int, staff_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE tickets SET claimed_by=? WHERE channel_id=?", (str(staff_id), str(channel_id)))
            await db.commit()

    async def get_all_open_tickets(self):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tickets WHERE status='open'") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def log_message(self, ticket_id: int, author_id: int, author_name: str, content: str, attachments: str = None, is_bot: bool = False):
        now = int(time.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO ticket_messages (ticket_id, author_id, author_name, content, is_bot, attachments, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ticket_id, str(author_id), author_name, content or "", 1 if is_bot else 0, attachments, now)
            )
            await db.commit()

    async def get_ticket_messages(self, ticket_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created_at ASC", (ticket_id,)) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def get_stats(self):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            stats = {}
            async with db.execute("SELECT COUNT(*) as c FROM tickets WHERE status='open'") as cur:
                stats["open"] = (await cur.fetchone())["c"]
            async with db.execute("SELECT COUNT(*) as c FROM tickets WHERE status='closed'") as cur:
                stats["closed"] = (await cur.fetchone())["c"]
            async with db.execute("SELECT COUNT(*) as c FROM tickets") as cur:
                stats["total"] = (await cur.fetchone())["c"]
            async with db.execute("SELECT COUNT(DISTINCT user_id) as c FROM tickets") as cur:
                stats["unique_users"] = (await cur.fetchone())["c"]
            return stats

    # --- Bans ---

    async def is_banned(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT 1 FROM ticket_bans WHERE user_id=?", (str(user_id),)) as cur:
                return await cur.fetchone() is not None

    async def ban_user(self, user_id: int, reason: str, banned_by: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ticket_bans (user_id, reason, banned_at, banned_by) VALUES (?, ?, ?, ?)",
                (str(user_id), reason, int(time.time()), str(banned_by))
            )
            await db.commit()

    async def unban_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM ticket_bans WHERE user_id=?", (str(user_id),))
            await db.commit()

    async def vacuum(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("VACUUM")
            await db.commit()

db = Database()
