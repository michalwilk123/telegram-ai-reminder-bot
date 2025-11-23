from typing import Callable

from ui.base import Errors
from utils import LogFunction


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
