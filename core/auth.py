from managers.storage_manager import StorageManager
from validation import is_token_valid


async def is_user_authenticated(storage_manager: StorageManager, user_id: str) -> bool:
    token_data = await storage_manager.get_user_token(user_id)
    if not token_data:
        return False
    return is_token_valid(token_data)
