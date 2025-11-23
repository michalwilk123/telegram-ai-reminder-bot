from time import time
from typing import Any

import httpx

from managers.config_manager import config_manager
from managers.storage_manager import StorageManager
from utils import LogFunction


async def save_user_token(
    storage_manager: StorageManager,
    user_id: str,
    token_data: dict[str, Any],
):
    # Security: Do not log token contents or keys to prevent exposure
    if 'refresh_token' not in token_data:
        # Log warning without exposing token data
        import sys
        print('[WARNING] Saving token WITHOUT refresh_token!', file=sys.stderr)
    await storage_manager.save_user_token(user_id, token_data)


async def get_user_token(storage_manager: StorageManager, user_id: str) -> dict[str, Any] | None:
    return await storage_manager.get_user_token(user_id)


async def require_user_token(
    storage_manager: StorageManager,
    user_id: str,
) -> dict[str, Any]:
    token_data = await storage_manager.get_user_token(user_id)
    if not token_data:
        raise ValueError('User not authenticated')
    return token_data


async def refresh_access_token(
    storage_manager: StorageManager,
    user_id: str,
    token_data: dict[str, Any],
    logger: LogFunction,
) -> dict[str, Any]:
    refresh_token = token_data.get('refresh_token')
    if not refresh_token:
        logger(f'No refresh token available for user {user_id}', 'error')
        raise ValueError('No refresh token available')

    logger(f'Refreshing access token for user {user_id}', 'info')
    logger(
        f'Token expires_at: {token_data.get("expires_at")}, current time: {int(time())}', 'debug'
    )

    async with httpx.AsyncClient() as client:
        logger(f'Sending token refresh request to Google OAuth for user {user_id}', 'debug')
        response = await client.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': config_manager.google_oauth2_client_id,
                'client_secret': config_manager.google_oauth2_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
        )

        if response.status_code != 200:
            logger(
                f'Token refresh failed for user {user_id}: {response.status_code} - {response.text}',
                'error',
            )
            raise ValueError(f'Failed to refresh token: {response.text}')

        logger(f'Token refresh successful for user {user_id}', 'info')
        new_token_data = response.json()

        token_data['access_token'] = new_token_data['access_token']
        token_data['expires_at'] = int(time()) + new_token_data.get('expires_in', 3600)

        if 'refresh_token' in new_token_data:
            token_data['refresh_token'] = new_token_data['refresh_token']
            logger(f'New refresh token received for user {user_id}', 'debug')

        logger(f'Saving refreshed token to database for user {user_id}', 'debug')
        await storage_manager.save_user_token(user_id, token_data)
        logger(
            f'Token refreshed and saved successfully for user {user_id}. New expires_at: {token_data["expires_at"]}',
            'info',
        )

        return token_data


async def get_valid_token(
    storage_manager: StorageManager,
    user_id: str,
    logger: LogFunction,
) -> dict[str, Any] | None:
    logger(f'Getting valid token for user {user_id}', 'debug')
    token_data = await storage_manager.get_user_token(user_id)
    if not token_data:
        logger(f'No token found in database for user {user_id}', 'warning')
        return None

    expires_at = token_data.get('expires_at', 0)
    current_time = int(time())

    if expires_at:
        time_until_expiry = expires_at - current_time
        logger(f'Token for user {user_id} expires in {time_until_expiry} seconds', 'debug')

        # Refresh if expired or expiring soon (within 5 minutes)
        # OR if we have a negative time_until_expiry (definitely expired)
        if expires_at < current_time + 300:
            logger(
                f'Token for user {user_id} is expired or expiring soon (within 5 minutes), refreshing...',
                'info',
            )
            try:
                token_data = await refresh_access_token(
                    storage_manager, user_id, token_data, logger
                )
            except Exception as e:
                logger(f'Failed to refresh token for user {user_id}: {e}', 'error')
                # If refresh failed and token is definitely expired, return None
                if time_until_expiry < 0:
                    logger(
                        'Token is definitely expired and refresh failed. Returning None.', 'error'
                    )
                    return None
                # If we can't refresh but token is "technically" not expired yet (between now and +5 mins),
                # we could return it, but it's risky. Let's return it for now.
                logger(
                    f'Refresh failed but token might still be marginally valid for {time_until_expiry}s. Returning old token.',
                    'warning',
                )
        else:
            logger(f'Token for user {user_id} is still valid', 'debug')
    else:
        logger(f'No expires_at timestamp in token for user {user_id}, assuming valid', 'warning')

    return token_data


async def revoke_google_token(
    token_data: dict[str, Any],
    logger: LogFunction,
) -> bool:
    access_token = token_data.get('access_token')
    if not access_token:
        logger('No access token to revoke', 'warning')
        return False

    logger('Revoking Google OAuth token', 'info')
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://oauth2.googleapis.com/revoke',
                params={'token': access_token},
                headers={'content-type': 'application/x-www-form-urlencoded'},
            )

            if response.status_code == 200:
                logger('Token revoked successfully', 'info')
                return True
            elif response.status_code == 400:
                logger(
                    'Token was already invalid or not revocable (400), considering revoked', 'info'
                )
                return True
            else:
                logger(
                    f'Token revocation failed: {response.status_code} - {response.text}', 'warning'
                )
                return False
    except Exception as e:
        logger(f'Error revoking token: {e}', 'error')
        return False


async def delete_user_token(
    storage_manager: StorageManager,
    user_id: str,
    logger: LogFunction,
) -> bool:
    logger(f'Deleting token for user {user_id}', 'info')
    token_data = await storage_manager.get_user_token(user_id)

    if token_data:
        await revoke_google_token(token_data, logger)

    success = await storage_manager.delete_user_token(user_id)
    if success:
        logger(f'Token deleted successfully for user {user_id}', 'info')
    else:
        logger(f'No token found to delete for user {user_id}', 'warning')

    return success
