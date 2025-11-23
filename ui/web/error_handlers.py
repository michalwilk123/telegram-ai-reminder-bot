from typing import Callable

from starlette.responses import HTMLResponse, Response

from ui.base import Errors
from utils import LogFunction


def create_error_response(error_message: str, status_code: int, debug: bool) -> Response:
    if debug:
        body = f'<h1>Error</h1><p>{error_message}</p><p><a href="/">Home</a></p>'
    else:
        body = (
            '<h1>Something went wrong</h1><p>Please try again later.</p><p><a href="/">Home</a></p>'
        )

    return HTMLResponse(body, status_code=status_code)


def build_validation_on_errors(action: str, logger: LogFunction) -> Callable[[Errors], None]:
    def on_errors(errors: Errors) -> None:
        messages: list[str] = []
        for err in errors:
            text = str(err).strip()
            if not text:
                continue
            for line in text.splitlines():
                line = line.strip()
                if line:
                    messages.append(line)

        count = len(messages) if messages else len(errors)
        error_summary = f'{count} Validation errors in {action}:'

        logger(error_summary, 'error')
        for msg in messages if messages else (str(e) for e in errors):
            logger(f'- {msg}', 'error')

    return on_errors
