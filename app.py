"""
Paradise Guest House - Flask Application
Main application file with routes and booking handling
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import init_db, save_booking, get_all_bookings, check_date_availability, get_booked_dates

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'paradise_guest_house_secret_key_2024'

# Admin credentials (change these!)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'paradise2024'

# Initialize database on startup
init_db()


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
        name = request.form.get('name')
        phone = request.form.get('phone')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        booking_type = request.form.get('booking_type')
        
        # Validate form data
        if not all([name, phone, start_date, end_date, booking_type]):
            flash('Please fill in all fields!', 'error')
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
    booked_dates = get_booked_dates()
    return render_template('book.html', booked_dates=booked_dates)


@app.route('/api/check-availability', methods=['POST'])
def check_availability():
    """
    API endpoint to check if dates are available.
    Returns JSON with availability status.
    """
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing dates'}), 400
    
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
    Admin page to view all bookings
    Protected with simple username/password
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # Get all bookings from database
            bookings = get_all_bookings()
            total_revenue = sum(b['price'] for b in bookings) if bookings else 0
            return render_template('admin.html', bookings=bookings, total_revenue=total_revenue)
        else:
            flash('Invalid credentials!', 'error')
            return redirect(url_for('admin'))
    
    # Show login form
    return render_template('admin_login.html')


# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    # Run in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5000)
