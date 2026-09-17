import sqlite3
from datetime import datetime, timezone


DATABASE_NAME = "bot.db"


def get_connection():
    return sqlite3.connect(DATABASE_NAME)


def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_premium INTEGER DEFAULT 0,
            premium_until TEXT,
            searches_today INTEGER DEFAULT 0,
            last_search_date TEXT,
            referral_count INTEGER DEFAULT 0,
            referral_rewards_given INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referred_user_id INTEGER PRIMARY KEY,
            referrer_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Add new columns if you already had an older bot.db
    try:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN referral_count INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN referral_rewards_given INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    connection.commit()
    connection.close()


def add_user(user_id, username=None, first_name=None):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO users
        (
            user_id,
            username,
            first_name
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        username,
        first_name
    ))

    created = cursor.rowcount > 0

    # Update user information if user already exists
    cursor.execute("""
        UPDATE users
        SET
            username = ?,
            first_name = ?
        WHERE user_id = ?
    """, (
        username,
        first_name,
        user_id
    ))

    connection.commit()
    connection.close()

    return created


def get_user(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            user_id,
            username,
            first_name,
            is_premium,
            premium_until,
            searches_today,
            last_search_date,
            referral_count,
            referral_rewards_given
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    user = cursor.fetchone()

    connection.close()

    return user


def set_premium(user_id, premium_until):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET
            is_premium = 1,
            premium_until = ?
        WHERE user_id = ?
    """, (
        premium_until,
        user_id
    ))

    connection.commit()
    connection.close()


def remove_premium(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET
            is_premium = 0,
            premium_until = NULL
        WHERE user_id = ?
    """, (user_id,))

    connection.commit()
    connection.close()


def is_premium(user_id):

    user = get_user(user_id)

    if not user:
        return False

    is_premium_value = user[3]
    premium_until = user[4]

    if not is_premium_value or not premium_until:
        return False

    try:

        expiry = datetime.fromisoformat(
            premium_until
        )

        now = datetime.now(timezone.utc)

        if expiry > now:
            return True

        remove_premium(user_id)

        return False

    except Exception:

        return False


def can_search(user_id, free_limit=10):

    if is_premium(user_id):
        return True

    user = get_user(user_id)

    if not user:
        return True

    searches_today = user[5]
    last_search_date = user[6]

    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    if last_search_date != today:

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE users
            SET
                searches_today = 0,
                last_search_date = ?
            WHERE user_id = ?
        """, (
            today,
            user_id
        ))

        connection.commit()
        connection.close()

        return True

    return searches_today < free_limit


def record_search(user_id):

    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET
            searches_today = searches_today + 1,
            last_search_date = ?
        WHERE user_id = ?
    """, (
        today,
        user_id
    ))

    connection.commit()
    connection.close()


def add_referral(referrer_id, referred_user_id):

    # Self-referral protection
    if referrer_id == referred_user_id:
        return False, 0

    connection = get_connection()
    cursor = connection.cursor()

    # Make sure the referred user exists
    cursor.execute("""
        SELECT user_id
        FROM users
        WHERE user_id = ?
    """, (referred_user_id,))

    if not cursor.fetchone():

        connection.close()
        return False, 0

    # A user can only be referred once
    cursor.execute("""
        SELECT referred_user_id
        FROM referrals
        WHERE referred_user_id = ?
    """, (referred_user_id,))

    if cursor.fetchone():

        connection.close()

        user = get_user(referrer_id)

        if user:
            return False, user[7]

        return False, 0

    # Make sure referrer exists
    cursor.execute("""
        SELECT user_id
        FROM users
        WHERE user_id = ?
    """, (referrer_id,))

    if not cursor.fetchone():

        connection.close()
        return False, 0

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cursor.execute("""
        INSERT INTO referrals
        (
            referred_user_id,
            referrer_user_id,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        referred_user_id,
        referrer_id,
        now
    ))

    cursor.execute("""
        UPDATE users
        SET referral_count = referral_count + 1
        WHERE user_id = ?
    """, (referrer_id,))

    cursor.execute("""
        SELECT referral_count
        FROM users
        WHERE user_id = ?
    """, (referrer_id,))

    result = cursor.fetchone()

    referral_count = result[0] if result else 0

    connection.commit()
    connection.close()

    return True, referral_count


def get_referral_info(user_id):

    user = get_user(user_id)

    if not user:
        return 0, 0

    referral_count = user[7]
    rewards_given = user[8]

    return referral_count, rewards_given


def mark_referral_reward_given(user_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE users
        SET referral_rewards_given =
            referral_rewards_given + 1
        WHERE user_id = ?
    """, (user_id,))

    connection.commit()
    connection.close()