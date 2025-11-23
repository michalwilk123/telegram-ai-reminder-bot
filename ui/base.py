from __future__ import annotations

from typing import Callable


class ValidationError(Exception):
    pass


Errors = list[ValidationError]


def noop_on_errors(_: Errors) -> None:
    pass


class BaseValidator:
    def __init__(
        self, raises: bool | type[Exception], on_errors: Callable[[Errors], None] = noop_on_errors
    ):
        self._errors: Errors = []
        self._raises = raises
        self._on_errors = on_errors

    def _add_error(self, message: str) -> None:
        self._errors.append(ValidationError(message))

    def execute(self) -> bool:
        if not self._errors:
            return True

        self._on_errors(self._errors)

        if self._raises is False:
            return False
        elif self._raises is True:
            raise ExceptionGroup('Multiple validation errors occurred', self._errors)
        else:
            exc_group = ExceptionGroup('Multiple validation errors occurred', self._errors)
            error_messages = '\n'.join(str(e) for e in self._errors)
            raise self._raises(error_messages) from exc_group
