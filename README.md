# CompBot

A Telegram chatbot that provides compliments and maintains conversations with users.

## Database Implementation

This application uses PostgreSQL for data storage. The implementation migrates any existing JSON data to PostgreSQL on startup, and then operates exclusively with PostgreSQL.

## Requirements

- Python 3.8+
- PostgreSQL
- Telegram Bot Token

## Installation

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

2. Set up PostgreSQL:

   - Create a new PostgreSQL user and database
   - Update the database configuration in `compbot.py` if needed:

```python
DB_CONFIG = {
    "dbname": "compbot",  # Your database name
    "user": "postgres",    # Your PostgreSQL username
    "password": "postgres", # Your PostgreSQL password
    "host": "localhost",
    "port": "5432"
}
```

## Features

- PostgreSQL database for reliable, scalable storage
- Automatic migration of data from JSON to PostgreSQL (one-time on first run)
- Improved error handling and logging
- Telegram integration for user interactions
- Scheduled compliments using AI language models
- Personalized responses to user messages

## Usage

Run the bot:

```bash
python compbot.py
```

The application will log both to the console and to a `compbot.log` file.

## PostgreSQL Setup

### Mac

1. Install PostgreSQL using Homebrew:

```bash
brew install postgresql@14
```

2. Start the PostgreSQL service:

```bash
brew services start postgresql
```

3. Create a user and database:

```bash
createuser -s postgres
createdb compbot
```

4. Set a password for the postgres user:

```bash
psql -U postgres
ALTER USER postgres WITH PASSWORD 'postgres';
\q
```

## How It Works

- The application uses PostgreSQL as its primary database
- First-time setup automatically migrates any existing JSON data to PostgreSQL
- After migration, the JSON files are renamed with a `.bak` extension to prevent re-migration
- Comprehensive error handling ensures robust operation
