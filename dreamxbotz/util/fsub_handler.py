from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from info import FSUB_PICS, FSUB_TIMEOUT
import logging as LOGGER

scheduler = AsyncIOScheduler(timezone="UTC")
#scheduler.start()

async def perform():
    """
    Periodically refresh ForceSub invite links.
    Reads all entries from DB, revokes expired links, and regenerates them.
    """
    from database.force_sub import force_db
    from dreamxbotz import Bot
    #LOGGER.info(f"Bot dirs:\n{dir(Bot)}")
    Bot = Bot.dreamxbotz
    now = datetime.utcnow()
    LOGGER.info("⏳ Checking ForceSub links...")

    docs = await force_db.get_all()
    _fsub = await force_db.get_fsub_timeout()
    if _fsub:
        FSUB_TIMEOUT = _fsub
    if not docs:
        LOGGER.info("No ForceSub entries found.")
        return

    for doc in docs:
        for name, data in doc.items():
            if name == "_id":
                continue

            for ch in data.get("channels", []):
                channel_id = ch["_id"]
                exp = ch.get("exp")

                if not exp or now >= exp:
                    try:
                        old_link = ch.get("invite_link")

                        # Revoke old link if present
                        if old_link:
                            try:
                                await Bot.revoke_chat_invite_link(channel_id, old_link)
                            except Exception as e:
                                LOGGER.info(
                                    f"[ForceSub] Couldn’t revoke old link for {channel_id}: {e}"
                                )
                        elif old_link is None:
                            link = await Bot.export_chat_invite_link(channel_id)
                            _wha = await Bot.revoke_chat_invite_link(channel_id, link)
                            if _wha.is_revoked:
                                LOGGER.info(
                                    f"Manually revoked link for {channel_id}"
                                )

                        # Create a new link valid for FSUB_TIMEOUT seconds
                        new_invite = await Bot.create_chat_invite_link(
                            channel_id,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_TIMEOUT)
                        )

                        await force_db.update_fsub_link(
                            name, channel_id, new_invite.invite_link, FSUB_TIMEOUT
                        )

                        LOGGER.info(
                            f"[ForceSub] 🔁 Refreshed link for {channel_id} ({name})"
                        )

                    except Exception as e:
                        LOGGER.error(
                            f"[ForceSub] ❌ Failed to refresh {channel_id}: {e}"
                        )

    LOGGER.info("✅ ForceSub refresh cycle complete.")


def start_force_sub_scheduler():
    """Starts the periodic ForceSub link revoker + refesher"""
    if not FSUB_TIMEOUT:
        LOGGER.warning("FSUB_TIMEOUT not configured, skipping scheduler.")
        return

    scheduler.add_job(
        perform,
        "interval",
        seconds=FSUB_TIMEOUT,
        id="force_sub_refresh",
        replace_existing=True,
    )

    LOGGER.info(
        f"[ForceSub Scheduler] Started with interval {FSUB_TIMEOUT // 3600} hours."
    )
