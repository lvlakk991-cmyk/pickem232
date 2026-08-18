import httpx

from app.config import BOT_TOKEN


async def is_member(chat_username: str, user_tg_id: int) -> bool:
    """True if the user is a member/admin/creator of the channel; False otherwise
    (also False if the bot itself lacks access, so it fails safe)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params={"chat_id": chat_username, "user_id": user_tg_id})
            data = r.json()
    except Exception:
        return False
    if not data.get("ok"):
        return False
    status = data["result"]["status"]
    return status not in ("left", "kicked")
