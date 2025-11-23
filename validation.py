from time import time


def is_token_valid(token_data: dict) -> bool:
    if not token_data:
        return False

    expires_at = token_data.get('expires_at')
    if not expires_at:
        return False

    current_time = int(time())
    return current_time < expires_at


def ensure_token_expiry(token: dict) -> dict:
    if 'expires_at' not in token and 'expires_in' in token:
        token['expires_at'] = int(time()) + token['expires_in']
    return token
