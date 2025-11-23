import asyncio
from datetime import datetime
import random
from typing import Any, Callable, TypeAlias, TypeVar

import httpx


def noop_log(_message: str, _level: str) -> None:
    pass


NOOP_LOG = noop_log

LogFunction: TypeAlias = Callable[[str, str], None]

T = TypeVar('T', bound=dict[str, Any])


def pick(source: dict[str, Any], keys: list[str]) -> T:
    """
    Creates a new dictionary with only the specified keys from the source dictionary.
    Only includes keys that exist in the source dictionary.

    Args:
        source: The source dictionary to pick from
        keys: List of keys to include in the result

    Returns:
        A new dictionary containing only the specified keys that exist in source
    """
    return {key: source[key] for key in keys if key in source}  # type: ignore[return-value]


def get_current_datetime() -> str:
    now = datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S')


class RetryTransport(httpx.AsyncHTTPTransport):
    def __init__(self, max_retries: int, logger: LogFunction = NOOP_LOG, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_retries = max_retries
        self.logger = logger

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = None
        for attempt in range(self.max_retries):
            try:
                response = await super().handle_async_request(request)

                # Retry on 5xx errors or 429 (rate limit)
                if response.status_code < 500 and response.status_code != 429:
                    return response

                if attempt < self.max_retries - 1:
                    # Non-deterministic backoff: base delay + jitter
                    base_delay = 2**attempt  # Exponential: 1, 2, 4 seconds
                    jitter = random.uniform(0, 1)  # Random jitter 0-1 seconds
                    delay = base_delay + jitter

                    self.logger(f'Retry attempt {attempt + 1} after {delay:.2f}s', 'warning')
                    await asyncio.sleep(delay)
                else:
                    return response

            except (httpx.ConnectError, httpx.TimeoutException):
                if attempt < self.max_retries - 1:
                    base_delay = 2**attempt
                    jitter = random.uniform(0, 1)
                    delay = base_delay + jitter

                    self.logger(
                        f'Connection error, retry {attempt + 1} after {delay:.2f}s', 'error'
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        if response is None:
            # Should be unreachable if max_retries >= 1 and no exception raised in last attempt
            raise httpx.ConnectError('Failed to connect after multiple attempts')

        return response


def create_http_client(logger: LogFunction = NOOP_LOG) -> httpx.AsyncClient:
    transport = RetryTransport(max_retries=3, logger=logger)
    return httpx.AsyncClient(transport=transport, timeout=30.0)
