import psycopg2
import psycopg2.extras
import os
import json
import logging

class Database:
    def __init__(self):
        # PostgreSQL connection parameters
        self.db_params = {
            "dbname": "compbot",
            "user": "postgres",
            "password": os.getenv("POSTGRES_PASSWORD"),
            "host": "localhost",
            "port": "5432"
        }
        
        # Initialize the database
        self.init_database()
        logging.info("Using PostgreSQL database")

    def init_database(self):
        """Initialize PostgreSQL database and tables"""
        try:
            # First, create the database if it doesn't exist
            conn = psycopg2.connect(
                dbname="postgres",
                user=self.db_params["user"],
                password=self.db_params["password"],
                host=self.db_params["host"],
                port=self.db_params["port"]
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Check if database exists, create if not
            cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (self.db_params["dbname"],))
            if not cursor.fetchone():
                cursor.execute(f"CREATE DATABASE {self.db_params['dbname']}")
            
            cursor.close()
            conn.close()
            
            # Connect to the compbot database and create tables
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create users table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    name VARCHAR(255),
                    last_name VARCHAR(255),
                    user_name VARCHAR(255),
                    join_date TIMESTAMP,
                    language VARCHAR(50) DEFAULT 'english',
                    personality_type VARCHAR(255) DEFAULT 'friendly',
                    personality_description TEXT DEFAULT '',
                    compliment_frequency TEXT DEFAULT 'daily',
                    active BOOLEAN DEFAULT TRUE,
                    bot_name VARCHAR(255) DEFAULT 'Romeo'
                )
            """)
            
            # Create user_history table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    role VARCHAR(50),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if we need to add new columns to existing users table
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'language'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN language VARCHAR(50) DEFAULT 'english'")
                logging.info("Added language column to users table")
                
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'personality_type'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN personality_type VARCHAR(255) DEFAULT 'friendly'")
                logging.info("Added personality_type column to users table")
                
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'personality_description'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN personality_description TEXT DEFAULT ''")
                logging.info("Added personality_description column to users table")
                
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'compliment_frequency'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN compliment_frequency TEXT DEFAULT 'daily'")
                logging.info("Added compliment_frequency column to users table")
                
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'active'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN active BOOLEAN DEFAULT TRUE")
                logging.info("Added active column to users table")
                
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'bot_name'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN bot_name VARCHAR(255) DEFAULT 'Romeo'")
                logging.info("Added bot_name column to users table")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Check for and migrate any existing JSON data
            self._migrate_json_to_postgres()
            
        except psycopg2.Error as e:
            logging.error(f"PostgreSQL initialization error: {e}")
            raise

    def _migrate_json_to_postgres(self):
        """Migrate data from JSON files to PostgreSQL if needed"""
        # Define paths for JSON data
        database_path = "user_database.json"
        hist_path = "user_hist"
        
        # Only migrate if JSON database exists
        if not os.path.exists(database_path):
            return
            
        try:
            # Load JSON user database
            with open(database_path, "r") as f:
                user_base = json.load(f)
                
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Migrate each user and their history
            for user_id, user_data in user_base.items():
                # Insert user
                cursor.execute("""
                    INSERT INTO users (user_id, name, last_name, user_name, join_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (
                    int(user_id),
                    user_data.get("name"),
                    user_data.get("last_name"),
                    user_data.get("user_name"),
                    user_data.get("join_date")
                ))
                
                # Get user history from JSON
                hist_path_file = os.path.join(hist_path, f"{user_id}_hist.json")
                if os.path.exists(hist_path_file):
                    with open(hist_path_file, "r") as f:
                        history = json.load(f)
                        
                    # Insert each history item
                    for msg in history:
                        cursor.execute("""
                            INSERT INTO user_history (user_id, role, content)
                            VALUES (%s, %s, %s)
                        """, (
                            int(user_id),
                            msg.get("role"),
                            msg.get("content")
                        ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logging.info("Successfully migrated data from JSON to PostgreSQL")
            
            # Rename the JSON files to backup versions to prevent re-migration
            os.rename(database_path, f"{database_path}.bak")
            if os.path.exists(hist_path):
                os.rename(hist_path, f"{hist_path}.bak")
                
        except Exception as e:
            logging.error(f"Error migrating data to PostgreSQL: {e}")

    def get_connection(self):
        """Get a connection to the PostgreSQL database"""
        try:
            conn = psycopg2.connect(**self.db_params)
            return conn
        except psycopg2.Error as e:
            logging.error(f"Error connecting to PostgreSQL database: {e}")
            raise

    def get_user(self, user_id):
        """Get a user by ID from the database"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return dict(user) if user else None

    def insert_user(self, update, name=None, language="english", personality_description="", frequency="daily"):
        """
        Insert a new user into the database with custom preferences
        
        Args:
            update: The Telegram update object
            name: Custom name for the user (optional)
            language: Language preference (default: english)
            personality_description: Custom personality description (default: empty)
            frequency: Compliment frequency (default: daily)
        
        Returns:
            The inserted user data as a dictionary
        """
        message = update.message
        user_id = message.from_user.id
        
        # Use provided name or fall back to first name
        if not name or len(name) == 0:
            name = message.from_user.first_name
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Insert user data
        cursor.execute("""
            INSERT INTO users (user_id, name, last_name, user_name, join_date, language, personality_type, personality_description, compliment_frequency, bot_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET name = EXCLUDED.name,
                last_name = EXCLUDED.last_name,
                user_name = EXCLUDED.user_name,
                language = EXCLUDED.language,
                personality_type = EXCLUDED.personality_type,
                personality_description = EXCLUDED.personality_description,
                compliment_frequency = EXCLUDED.compliment_frequency,
                bot_name = EXCLUDED.bot_name
        """, (
            user_id,
            name,
            message.from_user.last_name,
            message.from_user.username,
            message.date.strftime("%Y-%m-%d %H:%M:%S"),
            language,
            "custom",  # All personalities are now custom
            personality_description,
            frequency,
            "Romeo"
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return self.get_user(user_id)

    def update_user_language(self, user_id, language):
        """Update a user's language preference"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET language = %s WHERE user_id = %s
        """, (language, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return self.get_user(user_id)
        
    def update_user_personality(self, user_id, personality_type="custom", personality_description=""):
        """
        Update a user's personality preferences
        
        Args:
            user_id: The user's ID
            personality_type: The type of personality (default: custom)
            personality_description: Custom description of the personality
            
        Returns:
            The updated user data as a dictionary
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET personality_type = %s, personality_description = %s 
            WHERE user_id = %s
        """, (personality_type, personality_description, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return self.get_user(user_id)

    def update_compliment_frequency(self, user_id, frequency="daily"):
        """
        Update a user's compliment frequency preference
        
        Args:
            user_id: The user's ID
            frequency: The desired frequency (hourly, daily, often, rarely)
            
        Returns:
            The updated user data as a dictionary
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET compliment_frequency = %s 
            WHERE user_id = %s
        """, (frequency, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return self.get_user(user_id)
        
    def delete_user(self, user_id):
        """Delete a user and their history from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # First delete user history due to foreign key constraint
        cursor.execute("DELETE FROM user_history WHERE user_id = %s", (user_id,))
        
        # Then delete the user
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True

    def get_user_history(self, user_id):
        """Get user chat history from the database"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("""
            SELECT role, content FROM user_history 
            WHERE user_id = %s 
            ORDER BY timestamp
        """, (user_id,))
        
        history = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return [{"role": item["role"], "content": item["content"]} for item in history]

    def upsert_user_history(self, user_id, message):
        """Add a message to the user's chat history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_history (user_id, role, content)
            VALUES (%s, %s, %s)
        """, (
            user_id,
            message["role"],
            message["content"]
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    def update_user_bot_name(self, user_id, bot_name):
        """
        Update the bot name for a user
        
        Args:
            user_id: The user's Telegram ID
            bot_name: The name to set for the bot
            
        Returns:
            dict: Updated user record
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET bot_name = %s
            WHERE user_id = %s
            RETURNING *
        """, (bot_name, user_id))
        
        user = cursor.fetchone()
        conn.commit()
        cursor.close()
        
        if user:
            return self.get_user(user_id)
        return None

    @property
    def user_base(self):
        """Get all users as a dictionary"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Return as dictionary with user_id as key
        return {str(user["user_id"]): dict(user) for user in users}

    def hard_delete_user(self, user_id):
        """
        Permanently delete a user's account and all associated data
        
        Args:
            user_id: The user's ID
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # First delete from user_history due to foreign key constraint
            cursor.execute("DELETE FROM user_history WHERE user_id = %s", (user_id,))
            
            # Then delete from users table
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")
            return False