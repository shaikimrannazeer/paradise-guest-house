"""
Database module for Paradise Guest House
Handles SQLite database operations for bookings
"""

import sqlite3
import os

# Database file path
DATABASE = 'bookings.db'


def get_db_connection():
    """Create and return a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def init_db():
    """Initialize the database with the bookings table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            booking_type TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")


def save_booking(name, phone, start_date, end_date, booking_type):
    """
    Save a new booking to the database
    
    Args:
        name: Customer name
        phone: Customer phone number
        start_date: Booking start date (YYYY-MM-DD)
        end_date: Booking end date (YYYY-MM-DD)
        booking_type: 'Stay' or 'Function'
    
    Returns:
        booking_id: The ID of the newly created booking
        price: Total price
        num_days: Number of days booked
    """
    from datetime import datetime
    
    # Calculate number of days
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    num_days = (end - start).days
    if num_days < 1:
        num_days = 1  # Minimum 1 day
    
    # Calculate price based on booking type (per day)
    if booking_type == 'Stay':
        price_per_day = 4000
    else:  # Function
        price_per_day = 5500
    
    price = price_per_day * num_days
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO bookings (name, phone, start_date, end_date, booking_type, price)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, phone, start_date, end_date, booking_type, price))
    
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return booking_id, price, num_days


def get_all_bookings():
    """Get all bookings from the database"""
    conn = get_db_connection()
    bookings = conn.execute('SELECT * FROM bookings ORDER BY created_at DESC').fetchall()
    conn.close()
    return bookings


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
    
    # Find any bookings that overlap with the requested dates
    # Overlap occurs when: existing_start < requested_end AND existing_end > requested_start
    if exclude_booking_id:
        query = '''
            SELECT id, name, start_date, end_date, booking_type 
            FROM bookings 
            WHERE id != ? AND start_date < ? AND end_date > ?
        '''
        conflicting = conn.execute(query, (exclude_booking_id, end_date, start_date)).fetchall()
    else:
        query = '''
            SELECT id, name, start_date, end_date, booking_type 
            FROM bookings 
            WHERE start_date < ? AND end_date > ?
        '''
        conflicting = conn.execute(query, (end_date, start_date)).fetchall()
    
    conn.close()
    
    if conflicting:
        # Convert to list of dicts for easier handling
        conflicts = []
        for booking in conflicting:
            conflicts.append({
                'id': booking['id'],
                'name': booking['name'],
                'start_date': booking['start_date'],
                'end_date': booking['end_date'],
                'booking_type': booking['booking_type']
            })
        return False, conflicts
    
    return True, []


def get_booked_dates():
    """
    Get all booked date ranges for the calendar display.
    
    Returns:
        list: List of dicts with start_date and end_date
    """
    conn = get_db_connection()
    bookings = conn.execute('SELECT start_date, end_date FROM bookings').fetchall()
    conn.close()
    
    booked_dates = []
    for booking in bookings:
        booked_dates.append({
            'start': booking['start_date'],
            'end': booking['end_date']
        })
    
    return booked_dates


# Initialize database when module is imported
if __name__ == '__main__':
    init_db()
