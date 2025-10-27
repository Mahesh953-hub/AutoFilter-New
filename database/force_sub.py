# database/force_sub_db.py
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
from typing import List


class ForceSubDB:
    def __init__(self):
        self._client = AsyncIOMotorClient(DATABASE_URI)
        self.db = self._client[DATABASE_NAME]
        self.col = self.db.force_sub_channels
        self.settings = self.db.force_sub_settings  # for global FSUB timeout config

    # ----------------------------------------------------------------------
    # Force-Sub Channel Management
    # ----------------------------------------------------------------------

    async def set_fsub(
        self,
        name: str,
        channel_ids: List[int],
        user_id: int,
        expires_in: int = 3600,
        invite_link: str = None,
    ):
        """
        Save or update multiple ForceSub channels under a given name.
        Returns the saved document dict.
        """
        exp_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)

        data = {
            name: {
                "channels": [
                    {
                        "_id": cid,
                        "invite_link": invite_link or None,
                        "exp": exp_time,
                        "set_by": user_id,
                    }
                    for cid in channel_ids
                ],
                "last_updated": exp_time,
            }
        }

        await self.col.update_one({"_id": name}, {"$set": data}, upsert=True)
        return data

    async def get_fsub(self, name: str):
        """Retrieve all force-sub channels for the given name."""
        doc = await self.col.find_one({"_id": name})
        if not doc:
            return None

        info = doc.get(name)
        if not info or "channels" not in info:
            return None

        now = datetime.datetime.utcnow()
        for ch in info["channels"]:
            if ch.get("exp") and now > ch["exp"]:
                ch["expired"] = True

        return info

    async def update_fsub_link(
        self, name: str, channel_id: int, new_link: str, expires_in: int = 3600
    ):
        """
        Update the invite link & expiry for one specific channel ID
        under the given ForceSub group.
        """
        exp_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        await self.col.update_one(
            {"_id": name, f"{name}.channels._id": channel_id},
            {
                "$set": {
                    f"{name}.channels.$.invite_link": new_link,
                    f"{name}.channels.$.exp": exp_time,
                }
            },
        )

    async def delete_fsub(self, name: str):
        """Completely delete a ForceSub group."""
        await self.col.delete_one({"_id": name})

    async def get_all(self):
        """Return all ForceSub groups."""
        return await self.col.find({}).to_list(None)

    # ----------------------------------------------------------------------
    # Timeout Configuration Management
    # ----------------------------------------------------------------------

    async def set_fsub_timeout(self, seconds: int):
        """Set or update global ForceSub timeout value (used by scheduler)."""
        await self.settings.update_one(
            {"_id": "FSUB_TIMEOUT"},
            {
                "$set": {
                    "value": seconds,
                    "updated": datetime.datetime.utcnow(),
                }
            },
            upsert=True,
        )
        return seconds

    async def get_fsub_timeout(self, default: int = 14400):
        """Return current ForceSub timeout (in seconds), default = 4 hours."""
        doc = await self.settings.find_one({"_id": "FSUB_TIMEOUT"})
        return doc["value"] if doc and "value" in doc else default


# Instantiate global DB
force_db = ForceSubDB()
