"""
Database module for Paradise Guest House
Handles database operations for bookings
Uses Postgres when DATABASE_URL is set, otherwise a local SQLite file
"""

import sqlite3
import os
from datetime import datetime, timedelta, timezone

# Database file path
DATABASE = 'bookings.db'

# Postgres connection string, used in production
DATABASE_URL = os.environ.get('DATABASE_URL')

# Price per day for each booking type
PRICES = {'Stay': 4000, 'Function': 5500}

# Booking statuses
BOOKING_STATUSES = ('Pending', 'Confirmed', 'Cancelled')

# Dates are checked against India time, whatever timezone the server uses
IST = timezone(timedelta(hours=5, minutes=30))


class PostgresConnection:
    """Gives a Postgres connection the same interface as a SQLite one"""

    def __init__(self):
        import psycopg
        from psycopg.rows import dict_row
        self.conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)

    def execute(self, query, params=()):
        return self.conn.execute(query.replace('?', '%s'), params)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def get_db_connection():
    """Create and return a database connection"""
    if DATABASE_URL:
        return PostgresConnection()

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def lock_bookings(conn):
    """Start a transaction that stops other requests writing bookings"""
    if DATABASE_URL:
        conn.execute('LOCK TABLE bookings IN EXCLUSIVE MODE')
    else:
        conn.execute('BEGIN IMMEDIATE')


def init_db():
    """Initialize the database with the bookings table"""
    conn = get_db_connection()
    
    # Create bookings table
    id_column = 'SERIAL PRIMARY KEY' if DATABASE_URL else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS bookings (
            id {id_column},
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            booking_type TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add status column to databases created before it existed
    if not DATABASE_URL:
        columns = [row['name'] for row in conn.execute('PRAGMA table_info(bookings)')]
        if 'status' not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'")

    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def get_occupied_range(start_date, end_date):
    """
    Get the days a booking occupies as (first day, day after the last).
    The end date is checkout, so it stays free for the next guest.
    A same-day booking occupies that one day.
    """
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    return start, max(end, start + timedelta(days=1))


def validate_dates(start_date, end_date):
    """Return an error message for invalid dates, or None if they are fine"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return 'Please select valid dates.'

    if start < datetime.now(IST).date():
        return 'Start date cannot be in the past.'
    if end < start:
        return 'End date cannot be before start date.'
    return None


def find_conflicts(conn, start_date, end_date, exclude_booking_id=None):
    """Find active bookings that share a day with the given dates"""
    start, end = get_occupied_range(start_date, end_date)
    bookings = conn.execute(
        "SELECT id, name, start_date, end_date, booking_type FROM bookings WHERE status != 'Cancelled'"
    ).fetchall()

    conflicts = []
    for booking in bookings:
        if booking['id'] == exclude_booking_id:
            continue
        existing_start, existing_end = get_occupied_range(booking['start_date'], booking['end_date'])
        if existing_start < end and existing_end > start:
            conflicts.append(dict(booking))
    return conflicts


def save_booking(name, phone, start_date, end_date, booking_type):
    """
    Save a new booking to the database as Pending

    Args:
        name: Customer name
        phone: Customer phone number
        start_date: Booking start date (YYYY-MM-DD)
        end_date: Booking end date (YYYY-MM-DD)
        booking_type: 'Stay' or 'Function'

    Returns:
        booking_id: The ID of the new booking, or None if the dates were taken
        price: Total price
        num_days: Number of days booked
    """
    start, end = get_occupied_range(start_date, end_date)
    num_days = (end - start).days
    price = PRICES[booking_type] * num_days

    conn = get_db_connection()
    try:
        # Hold the write lock so two requests cannot both take the same dates
        lock_bookings(conn)
        if find_conflicts(conn, start_date, end_date):
            conn.rollback()
            return None, 0, 0

        cursor = conn.execute('''
            INSERT INTO bookings (name, phone, start_date, end_date, booking_type, price)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
        ''', (name, phone, start_date, end_date, booking_type, price))
        booking_id = cursor.fetchone()['id']
        conn.commit()
    finally:
        conn.close()

    return booking_id, price, num_days


def get_all_bookings():
    """Get all bookings from the database"""
    conn = get_db_connection()
    bookings = conn.execute('SELECT * FROM bookings ORDER BY created_at DESC').fetchall()
    conn.close()
    return bookings


def update_booking_status(booking_id, status):
    """
    Change a booking's status.

    Returns:
        bool: False if the booking is missing, or reopening it would clash
    """
    conn = get_db_connection()
    try:
        lock_bookings(conn)
        booking = conn.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,)).fetchone()
        if booking is None:
            conn.rollback()
            return False
        if status != 'Cancelled' and find_conflicts(conn, booking['start_date'], booking['end_date'], booking_id):
            conn.rollback()
            return False

        conn.execute('UPDATE bookings SET status = ? WHERE id = ?', (status, booking_id))
        conn.commit()
    finally:
        conn.close()
    return True


def check_date_availability(start_date, end_date, exclude_booking_id=None):
    """
    Check if the given date range is available for booking.

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        exclude_booking_id: Optional booking ID to exclude (for editing bookings)

    Returns:
        tuple: (is_available: bool, conflicting_bookings: list)
    """
    conn = get_db_connection()
    conflicts = find_conflicts(conn, start_date, end_date, exclude_booking_id)
    conn.close()
    return not conflicts, conflicts


def get_booked_days():
    """
    Get every occupied day for the calendar display.

    Returns:
        list: Sorted date strings (YYYY-MM-DD)
    """
    conn = get_db_connection()
    bookings = conn.execute(
        "SELECT start_date, end_date FROM bookings WHERE status != 'Cancelled'"
    ).fetchall()
    conn.close()

    booked_days = set()
    for booking in bookings:
        day, end = get_occupied_range(booking['start_date'], booking['end_date'])
        while day < end:
            booked_days.add(day.isoformat())
            day += timedelta(days=1)

    return sorted(booked_days)


# Initialize database when module is imported
if __name__ == '__main__':
    init_db()
