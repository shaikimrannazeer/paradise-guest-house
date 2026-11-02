"""
Paradise Guest House - Flask Application
Main application file with routes and booking handling
"""

import hmac
import os
import re
import secrets
import urllib.parse
import urllib.request

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from database import (init_db, save_booking, get_all_bookings, check_date_availability, get_booked_days,
                      update_booking_status, validate_dates, PRICES, BOOKING_STATUSES)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Admin credentials come from the environment. Without a password, login stays disabled.
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

# WhatsApp booking alerts stay off until the API key is set
CALLMEBOT_API_KEY = os.environ.get('CALLMEBOT_API_KEY')
WHATSAPP_ALERT_PHONE = os.environ.get('WHATSAPP_ALERT_PHONE', '919490025226')

# Initialize database on startup
init_db()


def normalize_phone(phone):
    """Return a 10-digit Indian mobile number, or None if it is invalid"""
    digits = re.sub(r'[\s()+-]', '', phone or '')
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    return digits if re.fullmatch(r'[6-9][0-9]{9}', digits) else None


def send_whatsapp_alert(booking_id, name, phone, start_date, end_date, booking_type, price, num_days):
    """Send the owner a WhatsApp alert. A failure must never stop the booking."""
    if not CALLMEBOT_API_KEY:
        return

    message = (f'🏡 New booking #{booking_id}\n'
               f'Name: {name}\n'
               f'Phone: +91{phone}\n'
               f'{booking_type}, {start_date} to {end_date} ({num_days} day{"s" if num_days > 1 else ""})\n'
               f'Total: ₹{price:,}')
    query = urllib.parse.urlencode({'phone': WHATSAPP_ALERT_PHONE, 'text': message, 'apikey': CALLMEBOT_API_KEY})
    try:
        urllib.request.urlopen(f'https://api.callmebot.com/whatsapp.php?{query}', timeout=5).close()
    except OSError as error:
        # Log only the error type, because the URL contains the API key
        print(f'WhatsApp alert failed for booking #{booking_id}: {type(error).__name__}')


def csrf_token():
    """Get the session's token for protecting admin forms"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']


def csrf_valid():
    """Check the token submitted with an admin form"""
    return hmac.compare_digest(request.form.get('csrf_token', ''), session.get('csrf_token', ''))


# ============================================
# ROUTES
# ============================================

@app.route('/')
def home():
    """Home page with welcome message"""
    return render_template('home.html')


@app.route('/facilities')
def facilities():
    """Facilities page showing all amenities"""
    return render_template('facilities.html')


@app.route('/book', methods=['GET', 'POST'])
def book():
    """
    Booking page with form
    GET: Display booking form
    POST: Process booking and save to database
    """
    if request.method == 'POST':
        # Get form data
        name = (request.form.get('name') or '').strip()
        phone = request.form.get('phone')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        booking_type = request.form.get('booking_type')
        
        # Validate form data
        if not all([name, phone, start_date, end_date, booking_type]):
            flash('Please fill in all fields!', 'error')
            return redirect(url_for('book'))
        
        phone = normalize_phone(phone)
        if not phone:
            flash('Please enter a valid 10-digit mobile number.', 'error')
            return redirect(url_for('book'))

        if booking_type not in PRICES:
            flash('Please select a valid booking type.', 'error')
            return redirect(url_for('book'))

        date_error = validate_dates(start_date, end_date)
        if date_error:
            flash(date_error, 'error')
            return redirect(url_for('book'))

        # Check if dates are available
        is_available, conflicts = check_date_availability(start_date, end_date)
        
        if not is_available:
            # Format conflict message
            conflict_dates = []
            for conflict in conflicts:
                conflict_dates.append(f"{conflict['start_date']} to {conflict['end_date']}")
            
            flash(f'❌ Sorry, these dates are already booked! Conflicting dates: {", ".join(conflict_dates)}. Please select different dates.', 'error')
            return redirect(url_for('book'))
        
        # Save booking to database
        booking_id, price, num_days = save_booking(name, phone, start_date, end_date, booking_type)
        
        # Someone else took the dates since the check above
        if booking_id is None:
            flash('❌ Sorry, these dates were just booked. Please select different dates.', 'error')
            return redirect(url_for('book'))

        send_whatsapp_alert(booking_id, name, phone, start_date, end_date, booking_type, price, num_days)

        # Show success page
        return render_template('success.html', 
                               name=name, 
                               booking_id=booking_id,
                               booking_type=booking_type,
                               price=price,
                               num_days=num_days,
                               start_date=start_date,
                               end_date=end_date)
    
    # GET request - show booking form with booked dates
    booked_days = get_booked_days()
    return render_template('book.html', booked_days=booked_days)


@app.route('/api/check-availability', methods=['POST'])
def check_availability():
    """
    API endpoint to check if dates are available.
    Returns JSON with availability status.
    """
    data = request.get_json(silent=True) or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing dates'}), 400

    date_error = validate_dates(start_date, end_date)
    if date_error:
        return jsonify({'error': date_error}), 400
    
    is_available, conflicts = check_date_availability(start_date, end_date)
    
    if is_available:
        return jsonify({
            'available': True,
            'message': '✅ These dates are available!'
        })
    else:
        conflict_info = []
        for conflict in conflicts:
            conflict_info.append({
                'start_date': conflict['start_date'],
                'end_date': conflict['end_date']
            })
        return jsonify({
            'available': False,
            'message': '❌ These dates are already booked. Please try different dates.',
            'conflicts': conflict_info
        })


@app.route('/contact')
def contact():
    """Contact page with phone and address"""
    return render_template('contact.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """
    Admin page to view and manage bookings
    Protected with a username/password login session
    """
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        if (ADMIN_PASSWORD
                and hmac.compare_digest(username.encode(), ADMIN_USERNAME.encode())
                and hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())):
            session.clear()
            session['admin'] = True
        else:
            flash('Invalid credentials!', 'error')
        return redirect(url_for('admin'))

    # Show login form
    if not session.get('admin'):
        return render_template('admin_login.html')

    # Get all bookings from database
    bookings = get_all_bookings()
    total_revenue = sum(b['price'] for b in bookings if b['status'] == 'Confirmed')
    pending_count = sum(1 for b in bookings if b['status'] == 'Pending')
    return render_template('admin.html', bookings=bookings, total_revenue=total_revenue,
                           pending_count=pending_count, csrf_token=csrf_token())


@app.route('/admin/bookings/<int:booking_id>/status', methods=['POST'])
def admin_update_status(booking_id):
    """Mark a booking as Pending, Confirmed or Cancelled"""
    if not session.get('admin') or not csrf_valid():
        return redirect(url_for('admin'))

    status = request.form.get('status')
    if status not in BOOKING_STATUSES or not update_booking_status(booking_id, status):
        flash(f'Could not update booking #{booking_id}. Its dates may now be taken.', 'error')
    return redirect(url_for('admin'))


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Log the admin out"""
    if csrf_valid():
        session.clear()
    return redirect(url_for('admin'))


# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    # Run in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5000)
