from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.database import SystemSetting

class SettingRepository:
    async def get_all(self, db: AsyncSession) -> dict[str, str]:
        result = await db.execute(select(SystemSetting))
        settings = result.scalars().all()
        return {s.setting_key: s.setting_value for s in settings if s.setting_value is not None}

    async def get(self, db: AsyncSession, key: str) -> str | None:
        result = await db.execute(select(SystemSetting).where(SystemSetting.setting_key == key))
        setting = result.scalars().first()
        return setting.setting_value if setting else None

    async def update_all(self, db: AsyncSession, settings_dict: dict[str, str]):
        # Get existing
        result = await db.execute(select(SystemSetting).where(SystemSetting.setting_key.in_(settings_dict.keys())))
        existing_settings = {s.setting_key: s for s in result.scalars().all()}

        for key, value in settings_dict.items():
            if key in existing_settings:
                existing_settings[key].setting_value = value
            else:
                new_setting = SystemSetting(setting_key=key, setting_value=value)
                db.add(new_setting)

setting_repo = SettingRepository()
