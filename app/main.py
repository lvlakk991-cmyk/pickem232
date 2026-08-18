import datetime as dt

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import database as db
from app.auth import validate_init_data
from app.telegram_api import is_member
from app.config import (
    BOT_TOKEN,
    ADMIN_IDS,
    DEV_MODE,
    ACHIEVEMENT_TIERS,
    MAX_TIER_POINTS,
    SUBSCRIBE_BONUS,
)

app = FastAPI(title="S2 Pick'em API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await db.init_db()


# --------------------------------------------------------- auth dependency
async def get_current_user(
    x_telegram_init_data: str = Header(default=""),
    x_dev_user_id: str = Header(default=""),
):
    """Resolves the caller from Telegram's signed initData (or, only in DEV_MODE,
    from a trusted-by-you X-Dev-User-Id header for local browser testing)."""
    tg_user = None

    if DEV_MODE and x_dev_user_id:
        tg_user = {"id": int(x_dev_user_id), "username": f"dev{x_dev_user_id}"}
    else:
        result = validate_init_data(x_telegram_init_data, BOT_TOKEN)
        if not result or not result["user"]:
            raise HTTPException(status_code=401, detail="Invalid or missing Telegram init data")
        tg_user = result["user"]

    row = await db.get_or_create_user(tg_user["id"], tg_user.get("username"))
    row["is_admin"] = tg_user["id"] in ADMIN_IDS
    row["tg_id"] = tg_user["id"]
    return row


async def require_admin(user: dict = Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ------------------------------------------------------------------- /me --
@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    channels = await db.list_channels()
    channel_status = []
    all_subscribed = True
    for ch in channels:
        ok = await is_member(ch["chat_username"], user["tg_id"])
        if not ok:
            all_subscribed = False
        channel_status.append(
            {
                "id": ch["id"],
                "name": ch["display_name"],
                "username": ch["chat_username"],
                "subscribed": ok,
            }
        )

    if all_subscribed and channels and not user["subscribed_bonus_claimed"]:
        await db.add_points(user["id"], SUBSCRIBE_BONUS)
        await db.mark_bonus_claimed(user["id"])
        user = await db.get_user_by_id(user["id"])

    return {
        "points": user["points"],
        "is_admin": user["is_admin"],
        "needs_subscription": channels and not all_subscribed,
        "channels": channel_status,
        "bonus_claimed": bool(user["subscribed_bonus_claimed"]),
    }


# --------------------------------------------------------------- pick'em --
@app.get("/api/pickem")
async def pickem(user: dict = Depends(get_current_user)):
    tournament = await db.get_active_tournament()
    if not tournament:
        return {"tournament": None, "matches": [], "progress": user["points"], "tiers": ACHIEVEMENT_TIERS, "max_tier_points": MAX_TIER_POINTS}

    matches = await db.get_pending_matches(tournament["id"])
    out = []
    for m in matches:
        predicted = await db.has_predicted(user["id"], m["id"])
        out.append(
            {
                "id": m["id"],
                "team1": m["team1"],
                "team2": m["team2"],
                "match_time": m["match_time"],
                "predicted": predicted,
            }
        )
    return {
        "tournament": {"name": tournament["name"], "stage": tournament["stage"]},
        "matches": out,
        "progress": min(user["points"], MAX_TIER_POINTS),
        "tiers": ACHIEVEMENT_TIERS,
        "max_tier_points": MAX_TIER_POINTS,
    }


class PredictionIn(BaseModel):
    match_id: int
    winner: str
    score1: int
    score2: int
    mvp: str


@app.post("/api/predict")
async def predict(body: PredictionIn, user: dict = Depends(get_current_user)):
    match = await db.get_match(body.match_id)
    if not match or match["status"] != "pending":
        raise HTTPException(400, "Match is not open for predictions")
    if body.winner not in (match["team1"], match["team2"]):
        raise HTTPException(400, "Winner must be one of the two teams")
    if await db.has_predicted(user["id"], body.match_id):
        raise HTTPException(400, "You already predicted this match")

    await db.add_prediction(
        user["id"], body.match_id, body.winner, body.score1, body.score2, body.mvp.strip()
    )
    return {"ok": True}


# ---------------------------------------------------------------- daily ---
@app.get("/api/daily")
async def daily(user: dict = Depends(get_current_user)):
    task = await db.get_today_task()
    if not task:
        return {"task": None}
    done = await db.has_completed_task(user["id"], task["id"])
    return {
        "task": {"id": task["id"], "description": task["description"], "points": task["points"]},
        "completed": done,
    }


class TaskCompleteIn(BaseModel):
    task_id: int


@app.post("/api/daily/complete")
async def daily_complete(body: TaskCompleteIn, user: dict = Depends(get_current_user)):
    tasks = await db.list_daily_tasks()
    task = next((t for t in tasks if t["id"] == body.task_id), None)
    if not task:
        raise HTTPException(404, "Task not found")
    if await db.has_completed_task(user["id"], body.task_id):
        raise HTTPException(400, "Already completed")
    await db.complete_task(user["id"], body.task_id, task["points"])
    return {"ok": True, "points": task["points"]}


# ------------------------------------------------------------------ top ---
@app.get("/api/top")
async def top():
    rows = await db.get_top_users(20)
    out = []
    for r in rows:
        total = r["total"] or 0
        correct = r["correct"] or 0
        out.append(
            {
                "username": r["username"] or f"id{r['tg_id']}",
                "points": r["points"],
                "total": total,
                "correct": correct,
                "accuracy": int(100 * correct / total) if total else 0,
            }
        )
    return {"top": out}


# ---------------------------------------------------------------- stats ---
@app.get("/api/stats")
async def stats(user: dict = Depends(get_current_user)):
    s = await db.get_user_prediction_stats(user["id"])
    total, correct = s["total"], s["correct"]
    return {
        "points": user["points"],
        "accuracy": int(100 * correct / total) if total else 0,
        "total": total,
        "correct": correct,
    }


# =========================================================== admin API ===
class TournamentIn(BaseModel):
    name: str
    stage: str = "Групповая стадия"


@app.get("/api/admin/tournaments")
async def admin_list_tournaments(_: dict = Depends(require_admin)):
    return {"tournaments": await db.list_tournaments()}


@app.post("/api/admin/tournaments")
async def admin_add_tournament(body: TournamentIn, _: dict = Depends(require_admin)):
    tid = await db.create_tournament(body.name, body.stage)
    await db.set_active_tournament(tid)
    return {"ok": True, "id": tid}


@app.post("/api/admin/tournaments/{tournament_id}/activate")
async def admin_activate_tournament(tournament_id: int, _: dict = Depends(require_admin)):
    await db.set_active_tournament(tournament_id)
    return {"ok": True}


class MatchIn(BaseModel):
    tournament_id: int
    team1: str
    team2: str
    match_time: str | None = None


@app.get("/api/admin/matches")
async def admin_list_matches(tournament_id: int, _: dict = Depends(require_admin)):
    return {"matches": await db.get_all_matches(tournament_id)}


@app.post("/api/admin/matches")
async def admin_add_match(body: MatchIn, _: dict = Depends(require_admin)):
    mid = await db.add_match(body.tournament_id, body.team1, body.team2, body.match_time)
    return {"ok": True, "id": mid}


class ResultIn(BaseModel):
    winner: str
    score1: int
    score2: int
    mvp: str


@app.post("/api/admin/matches/{match_id}/result")
async def admin_set_result(match_id: int, body: ResultIn, _: dict = Depends(require_admin)):
    match = await db.get_match(match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    if body.winner not in (match["team1"], match["team2"]):
        raise HTTPException(400, "Winner must be one of the two teams")
    await db.set_match_result(match_id, body.winner, body.score1, body.score2, body.mvp.strip())
    return {"ok": True}


class DailyTaskIn(BaseModel):
    description: str
    points: int


@app.get("/api/admin/daily-tasks")
async def admin_list_tasks(_: dict = Depends(require_admin)):
    return {"tasks": await db.list_daily_tasks()}


@app.post("/api/admin/daily-tasks")
async def admin_add_task(body: DailyTaskIn, _: dict = Depends(require_admin)):
    today = dt.date.today().isoformat()
    tid = await db.add_daily_task(today, body.description, body.points)
    return {"ok": True, "id": tid}


@app.delete("/api/admin/daily-tasks/{task_id}")
async def admin_delete_task(task_id: int, _: dict = Depends(require_admin)):
    await db.delete_daily_task(task_id)
    return {"ok": True}


class ChannelIn(BaseModel):
    chat_username: str
    display_name: str


@app.get("/api/admin/channels")
async def admin_list_channels(_: dict = Depends(require_admin)):
    return {"channels": await db.list_channels()}


@app.post("/api/admin/channels")
async def admin_add_channel(body: ChannelIn, _: dict = Depends(require_admin)):
    uname = body.chat_username if body.chat_username.startswith("@") else "@" + body.chat_username
    cid = await db.add_channel(uname, body.display_name)
    return {"ok": True, "id": cid}


@app.delete("/api/admin/channels/{channel_id}")
async def admin_delete_channel(channel_id: int, _: dict = Depends(require_admin)):
    await db.delete_channel(channel_id)
    return {"ok": True}


# --------------------------------------------------------- static files ---
# Must be mounted last so it doesn't shadow the /api/* routes above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
