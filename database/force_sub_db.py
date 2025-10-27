# force_sub_db.py
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME


class ForceSubDB:
    def __init__(self):
        self._client = AsyncIOMotorClient(DATABASE_URI)
        self.db = self._client[DATABASE_NAME]
        self.col = self.db.force_sub_channels

    async def set_fsub(self, name: str, channel_id: int, invite_link: str, user_id: int, expires_in: int = 3600):
        """
        Save or update a ForceSub entry.
        Returns the saved data dict.
        """
        exp_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)

        data = {
            name: {
                "_id": channel_id,
                "invite_link": invite_link,
                "exp": exp_time,
                "set_by": user_id
            }
        }

        await self.col.update_one(
            {"_id": name},
            {"$set": data},
            upsert=True
        )

        return data

    async def get_fsub(self, name: str):
        """Retrieve force sub data if exists (and valid)."""
        doc = await self.col.find_one({"_id": name})
        if not doc:
            return None

        info = doc.get(name)
        if not info:
            return None

        # Check expiry
        if info.get("exp") and datetime.datetime.utcnow() > info["exp"]:
            await self.col.update_one({"_id": name}, {"$unset": {f"{name}.invite_link": "", f"{name}.exp": ""}})
            info["expired"] = True
        return info

    async def update_fsub_link(self, name: str, new_link: str, expires_in: int = 3600):
        """Update only the invite link + expiry."""
        exp_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        await self.col.update_one(
            {"_id": name},
            {"$set": {f"{name}.invite_link": new_link, f"{name}.exp": exp_time}}
        )

    async def delete_fsub(self, name: str):
        """Delete a ForceSub entry completely."""
        await self.col.delete_one({"_id": name})


force_sub = ForceSubDB()
