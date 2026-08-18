"""Async SQLite data-access layer shared by the FastAPI backend and the bot."""
import datetime as dt
import aiosqlite

from app.config import DB_PATH, POINTS_WINNER, POINTS_SCORE, POINTS_MVP

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    points INTEGER NOT NULL DEFAULT 0,
    subscribed_bonus_claimed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_username TEXT NOT NULL,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'Групповая стадия',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL,
    team1 TEXT NOT NULL,
    team2 TEXT NOT NULL,
    match_time TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    winner TEXT,
    score1 INTEGER,
    score2 INTEGER,
    mvp TEXT,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    pred_winner TEXT NOT NULL,
    pred_score1 INTEGER,
    pred_score2 INTEGER,
    pred_mvp TEXT,
    points_earned INTEGER NOT NULL DEFAULT 0,
    scored INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, match_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

CREATE TABLE IF NOT EXISTS daily_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_date TEXT NOT NULL,
    description TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS daily_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    completed_at TEXT NOT NULL,
    UNIQUE(user_id, task_id)
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ---------------------------------------------------------------- users ----
async def get_or_create_user(tg_id: int, username: str | None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()
        if row:
            if username and row["username"] != username:
                await db.execute("UPDATE users SET username=? WHERE id=?", (username, row["id"]))
                await db.commit()
            return dict(row)
        await db.execute(
            "INSERT INTO users (tg_id, username, points, created_at) VALUES (?,?,0,?)",
            (tg_id, username, dt.datetime.utcnow().isoformat()),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        return dict(await cur.fetchone())


async def add_points(user_id: int, points: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET points = points + ? WHERE id=?", (points, user_id))
        await db.commit()


async def mark_bonus_claimed(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET subscribed_bonus_claimed=1 WHERE id=?", (user_id,))
        await db.commit()


async def get_user_by_id(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ------------------------------------------------------------- channels ----
async def add_channel(chat_username: str, display_name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO channels (chat_username, display_name) VALUES (?,?)",
            (chat_username, display_name),
        )
        await db.commit()
        return cur.lastrowid


async def list_channels() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM channels ORDER BY id")
        return [dict(r) for r in await cur.fetchall()]


async def delete_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE id=?", (channel_id,))
        await db.commit()


# ----------------------------------------------------------- tournaments ---
async def create_tournament(name: str, stage: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tournaments (name, stage, status, created_at) VALUES (?,?, 'active', ?)",
            (name, stage, dt.datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cur.lastrowid


async def get_active_tournament() -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tournaments WHERE status='active' ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_tournaments() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tournaments ORDER BY id DESC")
        return [dict(r) for r in await cur.fetchall()]


async def set_active_tournament(tournament_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tournaments SET status='finished' WHERE status='active'")
        await db.execute("UPDATE tournaments SET status='active' WHERE id=?", (tournament_id,))
        await db.commit()


# --------------------------------------------------------------- matches ---
async def add_match(tournament_id: int, team1: str, team2: str, match_time: str | None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO matches (tournament_id, team1, team2, match_time, status) "
            "VALUES (?,?,?,?, 'pending')",
            (tournament_id, team1, team2, match_time),
        )
        await db.commit()
        return cur.lastrowid


async def get_match(match_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM matches WHERE id=?", (match_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_pending_matches(tournament_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM matches WHERE tournament_id=? AND status='pending' ORDER BY id",
            (tournament_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def get_all_matches(tournament_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM matches WHERE tournament_id=? ORDER BY id", (tournament_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


async def set_match_result(match_id: int, winner: str, score1: int, score2: int, mvp: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE matches SET status='finished', winner=?, score1=?, score2=?, mvp=? WHERE id=?",
            (winner, score1, score2, mvp, match_id),
        )
        await db.commit()

        cur = await db.execute(
            "SELECT * FROM predictions WHERE match_id=? AND scored=0", (match_id,)
        )
        preds = [dict(r) for r in await cur.fetchall()]

        for p in preds:
            earned = 0
            if p["pred_winner"].strip().lower() == winner.strip().lower():
                earned += POINTS_WINNER
            if p["pred_score1"] == score1 and p["pred_score2"] == score2:
                earned += POINTS_SCORE
            if p["pred_mvp"] and mvp and p["pred_mvp"].strip().lower() == mvp.strip().lower():
                earned += POINTS_MVP

            await db.execute(
                "UPDATE predictions SET points_earned=?, scored=1 WHERE id=?", (earned, p["id"])
            )
            if earned:
                await db.execute(
                    "UPDATE users SET points = points + ? WHERE id=?", (earned, p["user_id"])
                )
        await db.commit()


# ----------------------------------------------------------- predictions ---
async def has_predicted(user_id: int, match_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM predictions WHERE user_id=? AND match_id=?", (user_id, match_id)
        )
        return (await cur.fetchone()) is not None


async def add_prediction(
    user_id: int, match_id: int, winner: str, score1: int, score2: int, mvp: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO predictions (user_id, match_id, pred_winner, pred_score1, pred_score2, pred_mvp) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, match_id, winner, score1, score2, mvp),
        )
        await db.commit()


async def get_user_prediction_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM predictions WHERE user_id=?", (user_id,))
        total = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM predictions WHERE user_id=? AND scored=1 AND points_earned>0",
            (user_id,),
        )
        correct = (await cur.fetchone())[0]
        return {"total": total, "correct": correct}


# --------------------------------------------------------------- ranking ---
async def get_top_users(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT u.id, u.tg_id, u.username, u.points,
                   COUNT(p.id) as total,
                   SUM(CASE WHEN p.scored=1 AND p.points_earned>0 THEN 1 ELSE 0 END) as correct
            FROM users u
            LEFT JOIN predictions p ON p.user_id = u.id
            GROUP BY u.id
            ORDER BY u.points DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in await cur.fetchall()]


# ----------------------------------------------------------- daily tasks ---
async def add_daily_task(task_date: str, description: str, points: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO daily_tasks (task_date, description, points, active) VALUES (?,?,?,1)",
            (task_date, description, points),
        )
        await db.commit()
        return cur.lastrowid


async def get_today_task() -> dict | None:
    today = dt.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM daily_tasks WHERE task_date=? AND active=1 ORDER BY id DESC LIMIT 1",
            (today,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_daily_tasks(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM daily_tasks ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in await cur.fetchall()]


async def delete_daily_task(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM daily_tasks WHERE id=?", (task_id,))
        await db.commit()


async def has_completed_task(user_id: int, task_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM daily_completions WHERE user_id=? AND task_id=?", (user_id, task_id)
        )
        return (await cur.fetchone()) is not None


async def complete_task(user_id: int, task_id: int, points: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO daily_completions (user_id, task_id, completed_at) VALUES (?,?,?)",
            (user_id, task_id, dt.datetime.utcnow().isoformat()),
        )
        await db.execute("UPDATE users SET points = points + ? WHERE id=?", (points, user_id))
        await db.commit()
