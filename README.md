# 🤖 Telegram AI Reminder Bot

![Bot Logo](botpic.jpg)

An intelligent AI-powered reminder bot that combines the convenience of Telegram with Google Calendar integration. Create one-time events or recurring reminders using natural language - the AI handles the rest.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

## ✨ Features

- 🧠 **AI-Powered Natural Language Processing** - Just tell the bot what you need in plain language
- 📅 **Google Calendar Integration** - Automatic sync with your Google Calendar for one-time events
- ⏰ **Cron-Based Recurring Reminders** - Set up daily, weekly, monthly, or custom recurring reminders
- 💬 **Dual Interface** - Use via Telegram bot or web dashboard
- 🌍 **Timezone Intelligence** - Automatically infers timezone from language and context
- 🔐 **OAuth2 Authentication** - Secure Google account integration
- 💾 **SQLite Database** - Lightweight, persistent storage for reminders and user data
- 🐳 **Docker Support** - Easy deployment with Docker and docker-compose

## 🏗️ Architecture

The project is built with a modular architecture, separating concerns into specialized managers:

```
telegram-ai-reminder-bot/
├── managers/              # Core business logic
│   ├── agent_manager.py        # 🧠 Pydantic AI agent (Gemini) - Natural language processing
│   ├── google_services_manager.py  # 📅 Google Calendar API integration
│   ├── schedule_manager.py     # ⏰ APScheduler - Cron job management
│   ├── storage_manager.py      # 💾 SQLAlchemy - SQLite database layer
│   └── config_manager.py       # ⚙️ Configuration and environment variables
├── ui/                    # User interfaces
│   ├── telegram/          # 📱 Telegram bot interface
│   │   ├── app.py             # Telegram bot setup
│   │   ├── handlers.py        # Command & message handlers
│   │   └── validator.py       # Input validation
│   └── web/              # 🌐 Web dashboard interface
│       ├── app.py             # Starlette web app & OAuth
│       ├── handlers.py        # HTTP route handlers
│       └── validator.py       # Form validation
├── core/                  # Authentication & token management
│   ├── auth.py                # OAuth2 flow
│   └── user_tokens.py         # Token refresh & validation
├── Dockerfile            # 🐳 Docker container configuration
├── docker-compose.yml    # 🐳 Docker orchestration
└── main.py               # 🚀 CLI entry point
```

### 🧩 Core Components

#### 1. **Agent Manager** (`managers/agent_manager.py`)
Uses **Pydantic AI** with Google's Gemini model to understand natural language:
- Interprets user requests in any language
- Automatically infers timezone from context (Polish → Europe/Warsaw, German → Europe/Berlin)
- Distinguishes between one-time events (→ Google Calendar) and recurring reminders (→ Cron)
- Maintains conversation history for context-aware responses
- Provides tools for reminder creation and calendar event management

#### 2. **Google Services Manager** (`managers/google_services_manager.py`)
Handles all Google Calendar operations:
- Creates calendar events with proper timezone handling
- Lists upcoming events (next 7 days)
- Manages OAuth2 access tokens
- Error handling for API failures and authentication issues

#### 3. **Schedule Manager** (`managers/schedule_manager.py`)
Manages recurring reminders using **APScheduler**:
- Parses and validates cron expressions
- Schedules jobs with AsyncIO support
- Loads existing reminders on startup
- Triggers reminder callbacks at scheduled times
- Handles job lifecycle (add, remove, update)

#### 4. **Storage Manager** (`managers/storage_manager.py`)
SQLite database layer using **SQLAlchemy**:
- **User Tokens**: Stores OAuth2 tokens with refresh capabilities
- **Reminders**: Persistent cron-based reminder storage
- **Conversation History**: Maintains AI conversation context (last 10 messages)
- **Telegram Mappings**: Links Telegram IDs to Google accounts
- Async database operations for non-blocking I/O

#### 5. **Telegram UI** (`ui/telegram/`)
Full-featured Telegram bot interface:
- `/start` - Initialize and authenticate
- `/menu` - Interactive menu with quick actions
- `/add` - Create new reminders or calendar events
- `/list` - View upcoming Google Calendar events
- `/reminders` - Manage recurring reminders
- Natural language conversation with AI agent
- OAuth2 flow via web portal

#### 6. **Web UI** (`ui/web/`)
Browser-based dashboard built with **Starlette**:
- Google OAuth2 login
- Chat interface with AI assistant
- Create calendar events via web form
- View upcoming events
- Session management

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Google Cloud Project with Calendar API enabled
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### 1. Clone the Repository

```bash
git clone https://github.com/michalwilk123/telegram-ai-reminder-bot.git
cd telegram-ai-reminder-bot
```

### 2. Install Dependencies

```bash
# Install uv if you haven't already
pip install uv

# Install project dependencies
uv sync
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Google OAuth2 (from Google Cloud Console)
GOOGLE_OAUTH2_CLIENT_ID=your_client_id
GOOGLE_OAUTH2_SECRET=your_client_secret
GOOGLE_API_KEY=your_gemini_api_key

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Application
SECRET_KEY=your_random_secret_key_for_sessions
REDIRECT_URL=http://localhost:9000

# Database (optional, defaults to SQLite)
DATABASE_URL=sqlite+aiosqlite:///app/data.db

# Debug mode (optional)
DEBUG=false
```

### 4. Run the Application

```bash
# Using uv (recommended)
uv run main.py run

# Or directly with Python
python server.py
```

The server will start on `http://localhost:9000`

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Using Docker Directly

```bash
# Build
docker build -t telegram-ai-reminder-bot .

# Run
docker run -d \
  -p 9000:9000 \
  -v $(pwd)/data.db:/app/data.db \
  -v $(pwd)/logs:/app/logs \
  --env-file .env \
  telegram-ai-reminder-bot
```

## 📖 Usage Examples

### Via Telegram

1. **Start the bot**: `/start`
2. **Authenticate**: Follow the OAuth2 link to connect your Google account
3. **Create reminders naturally**:
   ```
   "Remind me to call mom every Sunday at 3pm"
   → Creates recurring reminder with cron: 0 15 * * 0
   
   "Schedule dentist appointment tomorrow at 2pm for 30 minutes"
   → Creates Google Calendar event
   
   "Daily standup at 9:30am on weekdays"
   → Creates recurring reminder with cron: 30 9 * * 1-5
   ```

### Via Web Dashboard

1. Navigate to `http://localhost:9000`
2. Click "Login with Google"
3. Use the chat interface or create events via the form
4. View your upcoming calendar events

## 🧪 Development

### Run Tests

```bash
uv run main.py test
```

### Linting & Formatting

```bash
uv run main.py lint
```

### Type Checking

```bash
uv run main.py check
```

## 📦 Key Dependencies

- **pydantic-ai** - AI agent framework with Gemini integration
- **python-telegram-bot** - Telegram bot API wrapper
- **starlette** - Lightweight ASGI web framework
- **authlib** - OAuth2 authentication
- **sqlalchemy** - Database ORM with async support
- **apscheduler** - Advanced Python scheduler for cron jobs
- **httpx** - Modern async HTTP client
- **google-auth** - Google API authentication

## 🔐 Security & Privacy

- OAuth2 tokens are stored encrypted in the database
- AGPL-3.0 license ensures transparency and user freedom
- Sessions secured with secret key
- Access tokens automatically refreshed when expired
- User data isolated per account

## 🗺️ Roadmap

- [ ] Add more calendar providers (Outlook, iCal)
- [ ] Web UI improvements with modern frontend framework
- [ ] Reminder templates and categories
- [ ] Multi-language AI model support
- [ ] Voice message support in Telegram
- [ ] Reminder snooze functionality
- [ ] Export reminders to various formats

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This means:
- ✅ You can use, modify, and distribute this software freely
- ✅ You must share your source code if you provide the service over a network
- ✅ Any modifications must also be licensed under AGPL-3.0
- ✅ You must include the original copyright and license notice

See [LICENSE](LICENSE) for the full license text.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 👤 Author

**Michał Wilk** ([@michalwilk123](https://github.com/michalwilk123))

## 🙏 Acknowledgments

- Google Gemini for powering the AI agent
- Telegram Bot API for the messaging platform
- The amazing Python async ecosystem

---

Made with ❤️ using Python, AI, and a lot of ☕
