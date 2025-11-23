import json

from authlib.integrations.starlette_client import OAuth
import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route
from telegram.ext import Application

from managers.config_manager import config_manager
from managers.google_services_manager import GoogleServicesManager
from managers.schedule_manager import ScheduleManager
from managers.storage_manager import StorageManager
from ui.web import handlers
from ui.web.validator import WebValidationError, WebValidator
from utils import LogFunction

oauth = OAuth()

oauth.register(
    name='google',
    client_id=config_manager.google_oauth2_client_id,
    client_secret=config_manager.google_oauth2_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/calendar',
    },
    authorize_params={
        'access_type': 'offline',
        'prompt': 'consent',
    },
)


def build_redirect_uri(base_url: str) -> str:
    return f'{base_url.rstrip("/")}/auth'


LOGIN_PROMPT_HTML = '<a href="/login">Login with Google</a>'

HOMEPAGE_HTML = """<h1>Welcome {name}</h1>
<p>Email: {email}</p>
<img src="{picture}" width="100"/>
<br>
<a href="/chat">Chat with AI Assistant</a>
<br>
<a href="/create-event">Create New Event (Web)</a>
<br>
<a href="/events">List Upcoming Events (Web)</a>
<br>
<a href="/logout">Logout</a>"""

CREATE_EVENT_FORM_HTML = """<h1>Create New Event</h1>
<form action="/create-event" method="post">
    <label for="summary">Event Title:</label><br>
    <input type="text" id="summary" name="summary" required><br><br>

    <label for="start_time">Start Time:</label><br>
    <input type="datetime-local" id="start_time" name="start_time"
           value="{start_time}" required><br><br>

    <label for="end_time">End Time:</label><br>
    <input type="datetime-local" id="end_time" name="end_time"
           value="{end_time}" required><br><br>

    <label for="description">Description:</label><br>
    <textarea id="description" name="description"></textarea><br><br>

    <button type="submit">Create Event</button>
</form>
<br>
<a href="/">Back to Home</a>"""

EVENT_CREATED_HTML = (
    "<h1>Event Created!</h1><p><a href='{link}'>View Event</a></p><p><a href='/'>Home</a></p>"
)

EVENTS_LIST_HTML = """<h1>Upcoming Events</h1>
{events}
<br>
<p><a href="/create-event">Create New Event</a></p>
<p><a href="/">Back to Home</a></p>"""

NO_EVENTS_HTML = '<p>No upcoming events found for the next 7 days.</p>'

EVENT_LIST_ITEM_HTML = (
    "<li><strong>{start}</strong>: <a href='{link}' target='_blank'>{summary}</a></li>"
)

AUTH_ERROR_HTML = (
    '<h1>Authentication Error</h1><p>{message}</p><p><a href="/login">Try Again</a></p>'
)

VALIDATION_ERROR_HTML = (
    '<h1>Validation Error</h1><p>{message}</p><p><a href="/create-event">Try Again</a></p>'
)

GENERIC_ERROR_HTML = '<h1>Error</h1><p>{message}</p>'

TELEGRAM_SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Connected</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #f5f5f5;
        }
        .container {
            text-align: center;
            background-color: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #4CAF50;
            margin-bottom: 20px;
        }
        p {
            color: #666;
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✓ Success</h1>
        <p>Connected Telegram to the application.</p>
        <p>You can close this window.</p>
    </div>
</body>
</html>"""

CHAT_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>AI Assistant Chat</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        #chat-container {
            border: 1px solid #ccc;
            border-radius: 5px;
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            margin-bottom: 20px;
            background-color: #f9f9f9;
        }
        .message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 5px;
        }
        .user-message {
            background-color: #e3f2fd;
            text-align: right;
        }
        .assistant-message {
            background-color: #f5f5f5;
        }
        .message-label {
            font-weight: bold;
            margin-bottom: 5px;
        }
        #input-container {
            display: flex;
            gap: 10px;
        }
        #message-input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
        #send-button {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        #send-button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .back-link {
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>Chat with AI Assistant</h1>
    <div id="chat-container"></div>
    <div id="input-container">
        <input type="text" id="message-input" placeholder="Type your message..." />
        <button id="send-button">Send</button>
    </div>
    <div class="back-link">
        <a href="/">Back to Home</a>
    </div>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');

        function addMessage(text, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = isUser ? 'message user-message' : 'message assistant-message';
            
            const label = document.createElement('div');
            label.className = 'message-label';
            label.textContent = isUser ? 'You:' : 'Assistant:';
            
            const content = document.createElement('div');
            content.textContent = text;
            
            messageDiv.appendChild(label);
            messageDiv.appendChild(content);
            chatContainer.appendChild(messageDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            addMessage(message, true);
            messageInput.value = '';
            sendButton.disabled = true;

            try {
                const response = await fetch('/chat/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }

                const data = await response.json();
                addMessage(data.response, false);
            } catch (error) {
                addMessage('Error: Failed to send message', false);
            } finally {
                sendButton.disabled = false;
                messageInput.focus();
            }
        }

        sendButton.addEventListener('click', sendMessage);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        messageInput.focus();
    </script>
</body>
</html>"""


def create_error_response(error_message: str, status_code: int) -> Response:
    return HTMLResponse(AUTH_ERROR_HTML.format(message=error_message), status_code=status_code)


async def homepage(request: Request):
    validator = WebValidator(raises=False)
    user = validator.get_user_from_session(request)

    if not user:
        return HTMLResponse(LOGIN_PROMPT_HTML)

    return HTMLResponse(
        HOMEPAGE_HTML.format(
            name=user.get('name', 'User'), email=user.get('email'), picture=user.get('picture')
        )
    )


async def logout(request: Request):
    request.session.pop('user', None)
    request.session.pop('token', None)
    return RedirectResponse(url='/')


async def telegram_success(request: Request):
    return HTMLResponse(TELEGRAM_SUCCESS_HTML)


async def chat_page(request: Request):
    validator = WebValidator(raises=False)
    validator.user_authenticated(request).execute()

    if validator.has_errors():
        return RedirectResponse(url='/login')

    return HTMLResponse(CHAT_HTML)


async def chat_message(request: Request):
    validator = WebValidator(raises=False)
    validator.user_authenticated(request).execute()

    if validator.has_errors():
        return Response(
            content=json.dumps({'error': 'Not authenticated'}),
            media_type='application/json',
            status_code=401,
        )

    state = request.app.state
    agent_manager = state.agent_manager
    storage_manager = state.storage_manager
    logger: LogFunction = state.logger

    user = request.session.get('user', {})
    google_sub = user.get('sub')
    user_email = user.get('email', 'unknown')

    if not google_sub:
        return Response(
            content=json.dumps({'error': 'User ID not found'}),
            media_type='application/json',
            status_code=401,
        )

    try:
        body = await request.json()
        user_message = body.get('message', '')
        if not user_message:
            return Response(
                content=json.dumps({'error': 'Message is required'}),
                media_type='application/json',
                status_code=400,
            )

        logger(f'User {google_sub} sent message: {user_message}', 'info')

        response = await handlers.run_agent(
            agent_manager,
            storage_manager,
            google_sub,
            user_email,
            user_message,
        )

        return Response(content=json.dumps({'response': response}), media_type='application/json')

    except ValueError as e:
        logger(f'Error processing chat message: {str(e)}', 'error')
        return Response(
            content=json.dumps({'error': str(e)}), media_type='application/json', status_code=400
        )
    except Exception as e:
        logger(f'Error processing chat message: {str(e)}', 'error')
        return Response(
            content=json.dumps({'error': 'Internal server error'}),
            media_type='application/json',
            status_code=500,
        )


async def web_create_event_form(request: Request):
    validator = WebValidator(raises=False)
    validator.user_authenticated(request).execute()

    if validator.has_errors():
        return RedirectResponse(url='/login')

    start_default, end_default = handlers.get_create_event_form_defaults()

    return HTMLResponse(
        CREATE_EVENT_FORM_HTML.format(
            start_time=start_default.isoformat()[:16], end_time=end_default.isoformat()[:16]
        )
    )


async def web_create_event_post(request: Request):
    validator = WebValidator(raises=False)
    validator.user_authenticated(request).execute()

    if validator.has_errors():
        return RedirectResponse(url='/login')

    form_data = await request.form()
    state = request.app.state
    google_services_manager = state.google_services_manager
    logger: LogFunction = state.logger

    validator = WebValidator(raises=False)
    validator.event_form_valid(dict(form_data)).execute()

    access_token = validator.get_access_token_from_session(request)
    if not access_token or validator.has_errors():
        return create_error_response(str(validator.get_errors()), 401)

    form_data_validated = validator.get_form_data()

    # Get user's timezone from session, default to UTC if not available
    user = request.session.get('user', {})
    user_timezone = user.get('timezone', 'UTC')

    try:
        event = await handlers.create_calendar_event(
            google_services_manager,
            logger,
            access_token,
            form_data_validated['summary'],
            f'{form_data_validated["start_time"]}:00',
            f'{form_data_validated["end_time"]}:00',
            form_data_validated['description'],
            user_timezone,
        )
        html_link = event.get('htmlLink', '#')
        return HTMLResponse(EVENT_CREATED_HTML.format(link=html_link))

    except WebValidationError as ve:
        return HTMLResponse(VALIDATION_ERROR_HTML.format(message=str(ve)), status_code=400)
    except Exception as e:
        logger(f'Error creating event: {str(e)}', 'error')
        return HTMLResponse(
            GENERIC_ERROR_HTML.format(message=f'Error creating event: {str(e)}'), status_code=500
        )


async def web_list_events(request: Request):
    validator = WebValidator(raises=False)
    validator.user_authenticated(request).execute()

    if validator.has_errors():
        return RedirectResponse(url='/login')

    access_token = validator.get_access_token_from_session(request)
    if not access_token or validator.has_errors():
        return RedirectResponse(url='/login')

    state = request.app.state
    google_services_manager = state.google_services_manager
    logger: LogFunction = state.logger

    # Get user's timezone from session, default to UTC if not available
    user = request.session.get('user', {})
    user_timezone = user.get('timezone', 'UTC')

    try:
        events = await handlers.list_calendar_events(
            google_services_manager,
            access_token,
            user_timezone,
        )

        if not events:
            events_html = NO_EVENTS_HTML
        else:
            items = []
            for event in events:
                start = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
                summary = event.get('summary', '(No Title)')
                html_link = event.get('htmlLink', '#')
                items.append(
                    EVENT_LIST_ITEM_HTML.format(start=start, link=html_link, summary=summary)
                )
            events_html = '<ul>' + ''.join(items) + '</ul>'

        return HTMLResponse(EVENTS_LIST_HTML.format(events=events_html))

    except Exception as e:
        logger(f'Error listing events: {str(e)}', 'error')
        return HTMLResponse(
            GENERIC_ERROR_HTML.format(message=f'Error listing events: {str(e)}'), status_code=500
        )


async def login(request: Request):
    validator = WebValidator(raises=False)
    validator.user_authenticated(request).execute()

    if not validator.has_errors():
        return RedirectResponse(url='/')

    telegram_id = request.query_params.get('telegram_id')
    from_telegram = request.query_params.get('from_telegram')
    
    if telegram_id:
        request.session['telegram_id'] = telegram_id
    
    if from_telegram:
        request.session['from_telegram'] = from_telegram

    redirect_uri = build_redirect_uri(config_manager.redirect_url)

    return await oauth.google.authorize_redirect(
        request, redirect_uri, access_type='offline', prompt='consent'
    )


async def auth(request: Request):
    logger = request.app.state.logger
    storage_manager = request.app.state.storage_manager

    validator = WebValidator(raises=WebValidationError)

    if not validator.session_exists(request).execute():
        return create_error_response(
            'Session lost. This can happen when switching domains, blocking cookies, or using HTTP with secure cookies.',
            400,
        )

    validator = WebValidator(raises=WebValidationError)
    await validator.oauth_authorize_token(oauth, request)
    validator.ensure_token_expiry_set()

    try:
        validator.execute()
    except WebValidationError as e:
        logger(f'Authentication failed: {str(e)}', 'warning')
        return create_error_response(f'Authentication failed: {str(e)}', 400)

    token = validator.get_token()

    if token is None:
        return create_error_response('Failed to get token', 401)

    try:
        WebValidator(raises=WebValidationError).user_info_present(token).execute()
    except WebValidationError as e:
        return create_error_response(str(e), 500)

    user = token.get('userinfo')
    logger(f'User logged in: {user}', 'info')
    request.session['user'] = user
    request.session['token'] = token

    google_sub = user.get('sub')
    if google_sub:
        logger(f'Saving token for Google sub: {google_sub}', 'debug')
        await storage_manager.save_user_token(google_sub, token)
        logger(f'Saved token for user {google_sub}', 'info')

        telegram_id = request.session.get('telegram_id')
        if telegram_id:
            logger(f'Saving Telegram mapping: {telegram_id} -> {google_sub}', 'debug')
            await storage_manager.save_telegram_user_mapping(str(telegram_id), google_sub)
            logger(f'Saved Telegram mapping for user {telegram_id}', 'info')
            request.session.pop('telegram_id', None)

    from_telegram = request.session.get('from_telegram')
    if from_telegram:
        request.session.pop('from_telegram', None)
        return RedirectResponse(url='/telegram/success')

    return RedirectResponse(url='/')


middleware = [
    Middleware(
        SessionMiddleware,
        secret_key=config_manager.secret_key,
        https_only=not config_manager.debug,
        same_site='lax' if config_manager.debug else 'strict',
    )
]

routes = [
    Route('/', homepage, methods=['GET']),
    Route('/login', login, methods=['GET']),
    Route('/auth', auth, methods=['GET']),
    Route('/logout', logout, methods=['GET']),
    Route('/telegram/success', telegram_success, methods=['GET']),
    Route('/chat', chat_page, methods=['GET']),
    Route('/chat/message', chat_message, methods=['POST']),
    Route('/create-event', web_create_event_form, methods=['GET']),
    Route('/create-event', web_create_event_post, methods=['POST']),
    Route('/events', web_list_events, methods=['GET']),
]


def create_app(
    *,
    storage_manager: StorageManager,
    schedule_manager: ScheduleManager,
    google_services_manager: GoogleServicesManager,
    http_client: httpx.AsyncClient,
    logger: LogFunction,
    bot_application: Application,
) -> Starlette:
    app = Starlette(debug=config_manager.debug, routes=routes, middleware=middleware)
    app.state.storage_manager = storage_manager
    app.state.schedule_manager = schedule_manager
    app.state.google_services_manager = google_services_manager
    app.state.http_client = http_client
    app.state.logger = logger
    app.state.bot_application = bot_application
    return app
