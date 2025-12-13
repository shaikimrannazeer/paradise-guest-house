"""
Paradise Guest House - Flask Application
Main application file with routes and booking handling
"""

from flask import Flask, render_template, request, redirect, url_for, flash
from database import init_db, save_booking, get_all_bookings

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
    
    # GET request - show booking form
    return render_template('book.html')


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
