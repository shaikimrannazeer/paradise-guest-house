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


# Initialize database when module is imported
if __name__ == '__main__':
    init_db()
