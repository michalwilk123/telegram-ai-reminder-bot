from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request

from ui.base import BaseValidator, Errors, ValidationError, noop_on_errors
from validation import ensure_token_expiry, is_token_valid


class WebValidationError(ValidationError):
    pass


class WebValidator(BaseValidator):
    def __init__(
        self, raises: bool | type[Exception], on_errors: Callable[[Errors], None] = noop_on_errors
    ):
        super().__init__(raises, on_errors)
        self._form_data: dict[str, str] | None = None
        self._token: dict[str, Any] | None = None

    def has_errors(self) -> bool:
        return len(self._errors) > 0

    def get_errors(self) -> Errors:
        return self._errors

    def get_form_data(self) -> dict[str, str]:
        if self._form_data is None:
            raise ValueError('Form data not validated')
        return self._form_data

    def get_token(self) -> dict[str, Any] | None:
        return self._token

    def get_user_from_session(self, request: Request) -> dict[str, Any] | None:
        return request.session.get('user')

    def get_access_token_from_session(self, request: Request) -> str:
        token = request.session.get('token')
        if not token:
            raise WebValidationError('Token not found in session')

        access_token = token.get('access_token')
        if not access_token:
            raise WebValidationError('Access token not found in token data')

        return access_token

    def user_authenticated(self, request: Request) -> WebValidator:
        user = request.session.get('user')
        token = request.session.get('token')

        if not user:
            self._add_error('User not found in session')
            return self

        if not token:
            self._add_error('Token not found in session')
            return self

        if not is_token_valid(token):
            self._add_error('Token has expired')

        return self

    def session_exists(self, request: Request) -> WebValidator:
        if not request.session:
            self._add_error('Session not found. Cookies may be blocked or session expired')
        return self

    def token_has_access_token(self, request: Request) -> WebValidator:
        token = request.session.get('token')
        if not token:
            self._add_error('Token not found in session')
            return self

        access_token = token.get('access_token')
        if not access_token:
            self._add_error('Access token not found in token data')

        return self

    def user_info_present(self, token_data: dict) -> WebValidator:
        user_info = token_data.get('userinfo')
        if not user_info:
            self._add_error('User information not found in token data')
        return self

    def event_form_valid(self, form_data: dict) -> WebValidator:
        summary = form_data.get('summary', '').strip()
        start_time = form_data.get('start_time', '').strip()
        end_time = form_data.get('end_time', '').strip()
        description = form_data.get('description', '').strip()

        if not summary:
            self._add_error('Summary is required')

        if not start_time:
            self._add_error('Start time is required')

        if not end_time:
            self._add_error('End time is required')

        if not self._errors:
            try:
                start_dt = datetime.fromisoformat(start_time)
            except ValueError:
                self._add_error('Invalid start time format')
                return self

            try:
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                self._add_error('Invalid end time format')
                return self

            if end_dt <= start_dt:
                self._add_error('End time must be after start time')
                return self

            self._form_data = {
                'summary': summary,
                'start_time': start_time,
                'end_time': end_time,
                'description': description,
            }

        return self

    async def oauth_authorize_token(self, oauth: OAuth, request: Request) -> WebValidator:
        try:
            token = await oauth.google.authorize_access_token(request)
            self._token = ensure_token_expiry(token)
        except Exception as error:
            error_details = f'{type(error).__name__}: {str(error)}'
            self._add_error(error_details)

        return self

    def ensure_token_expiry_set(self) -> WebValidator:
        if self._token:
            self._token = ensure_token_expiry(self._token)
        return self


def validate_event_form(form_data: dict) -> dict[str, str]:
    validator = WebValidator(raises=WebValidationError)

    summary = form_data.get('summary', '').strip()
    start_time = form_data.get('start_time', '').strip()
    end_time = form_data.get('end_time', '').strip()
    description = form_data.get('description', '').strip()

    if not summary:
        validator._add_error('Summary is required')

    if not start_time:
        validator._add_error('Start time is required')

    if not end_time:
        validator._add_error('End time is required')

    validator.execute()

    try:
        start_dt = datetime.fromisoformat(start_time)
    except ValueError as exc:
        raise WebValidationError('Invalid start time format') from exc

    try:
        end_dt = datetime.fromisoformat(end_time)
    except ValueError as exc:
        raise WebValidationError('Invalid end time format') from exc

    if end_dt <= start_dt:
        raise WebValidationError('End time must be after start time')

    return {
        'summary': summary,
        'start_time': start_time,
        'end_time': end_time,
        'description': description,
    }


async def validate_oauth_token(oauth: OAuth, request: Request) -> dict[str, Any]:
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as error:
        error_details = f'{type(error).__name__}: {str(error)}'
        raise WebValidationError(error_details) from error

    return ensure_token_expiry(token)


def get_user_from_session(request: Request) -> dict[str, Any] | None:
    return request.session.get('user')


def get_access_token_from_session(request: Request) -> str:
    token = request.session.get('token')
    if not token:
        raise WebValidationError('Token not found in session')

    access_token = token.get('access_token')
    if not access_token:
        raise WebValidationError('Access token not found in token data')

    return access_token
