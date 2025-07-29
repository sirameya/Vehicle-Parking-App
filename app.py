import os
from flask import Flask, render_template, request, redirect, flash, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, ParkingLot, ParkingSpot, Reservation
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# ✅ Use absolute path to point to the correct database location
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'parking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Print path to confirm it's correct
print("[DEBUG] Using database at:", db_path)

db.init_app(app)

#Initialize Default Admin
def initialize_admin():
    existing_admin = User.query.filter_by(username='admin').first()
    if not existing_admin:
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created successfully")
    else:
        print("ℹ️ Admin already exists")


#  Home Page
# Log out the current user and clear the session

@app.route("/")
def home():
    return render_template("home.html")




# Admin dashboard: view/manage lots, users, reservations, and analytics

# Register (for the User Only)
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

# Admin: Create a new parking lot (and its spots)


        if User.query.filter_by(username=username).first():
            flash("Username already exists.")
            return redirect("/register")

        hashed_pw = generate_password_hash(password)
# Admin: Edit an existing parking lot (and adjust spots)
        user = User(username=username, password=hashed_pw, role='user')
        db.session.add(user)
        db.session.commit()
        flash("✅ Registration successful.")
        return redirect("/login")

# Admin: Delete a parking lot (only if all spots are empty)
    return render_template("register.html")

# Login (Shared User/Admin)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

# User dashboard: view available lots, reservations, and history

        session.clear()  # clear prev session data
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):

# Admin: View all spots in a specific parking lot (visual map)

            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            print(f"[DEBUG] Login successful, user_id: {session['user_id']}")
            if user.role == 'admin':
                session["admin_logged_in"] = True

# Admin: Delete a parking spot (only if it is available)

                flash("Admin login successful.")
                return redirect("/admin/dashboard")
            else:
                flash("User login successful.")
                return redirect("/user/dashboard")
        else:

# User: Reserve the first available spot in a parking lot

            flash("Invalid username or password.")
            return redirect("/login")

    return render_template("login.html")

# Direct Admin Login Route

# User: Release a reserved spot and calculate parking cost

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        session.clear()  # clear prev session data
        username = request.form["username"]
        password = request.form["password"]

# User: View reservation page for a specific lot (shows available spots)


        user = User.query.filter_by(username=username, role='admin').first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username

# Admin: View analytics and summary charts for all lots and users

            session["role"] = user.role
            session["admin_logged_in"] = True
            flash("Admin login successful.")
            return redirect("/admin/dashboard")
        else:
            flash("Invalid admin credentials.")
            return redirect("/admin/login")

    return render_template("admin_login.html")

# User: View personal parking analytics and summary charts


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect("/")

# Admin Dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get("role") != "admin":
        flash("Unauthorized access.")
        return redirect("/login")

    search = request.args.get('search', '').strip()
    user_search = request.args.get('user_search', '').strip()
    if search:
        parking_lots = ParkingLot.query.filter(
            (ParkingLot.lot_name.ilike(f'%{search}%')) |
            (ParkingLot.address.ilike(f'%{search}%')) |
            (ParkingLot.pincode.ilike(f'%{search}%')) |
            (ParkingLot.city.ilike(f'%{search}%'))
        ).all()
    else:
        parking_lots = ParkingLot.query.all()
    if user_search:
        users = User.query.filter(User.username.ilike(f'%{user_search}%')).all()
    else:
        users = User.query.all()
    reservations = Reservation.query.all()
    # Prepare summary data for charts
    from collections import defaultdict
    lot_names = [lot.lot_name for lot in parking_lots]
    lot_res_counts = defaultdict(int)
    for res in reservations:
        if res.spot and res.spot.lot:
            lot_res_counts[res.spot.lot.lot_name] += 1
    lot_chart_labels = lot_names
    lot_chart_data = [lot_res_counts[name] for name in lot_chart_labels]
    total_revenue = sum(res.total_cost for res in reservations if res.total_cost)
    active_users = len(set(res.user_id for res in reservations if res.leaving_timestamp is None))
    return render_template('admin_dashboard.html', parking_lots=parking_lots, users=users, reservations=reservations, lot_chart_labels=lot_chart_labels, lot_chart_data=lot_chart_data, total_revenue=total_revenue, active_users=active_users)

# Create Parking Lot
@app.route('/admin/create_lot', methods=['GET', 'POST'])
def create_lot():
    if session.get("role") != "admin":
        flash("Unauthorized access.")
        return redirect("/login")

    if request.method == 'POST':
        lot_name = request.form['lot_name']
        address = request.form['address']
        city = request.form['city']
        pincode = request.form['pincode']
        capacity = int(request.form['capacity'])
        price = float(request.form['price'])

        new_lot = ParkingLot(lot_name=lot_name, address=address, city=city, pincode=pincode, capacity=capacity, price=price)
        db.session.add(new_lot)
        db.session.commit()
        for i in range(capacity):
            new_spot = ParkingSpot(lot_id=new_lot.id, status="available")
            db.session.add(new_spot)
            db.session.commit()
        flash('✅ Parking lot created.')
        return redirect('/admin/dashboard')

    return render_template('create_lot.html')

#  Edit Parking Lot
@app.route('/admin/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if session.get("role") != "admin":
        flash("Unauthorized access.")
        return redirect("/login")

    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == 'POST':
        lot.lot_name = request.form['lot_name']
        lot.address = request.form['address']
        lot.city = request.form['city']
        lot.pincode = request.form['pincode']
        new_capacity = int(request.form['capacity'])
        old_capacity = lot.capacity
        lot.capacity = new_capacity
        lot.price = float(request.form['price'])
        db.session.commit()

        # Adjust ParkingSpot records if capacity changed
        if new_capacity > old_capacity:
            # Add new spots
            for i in range(old_capacity, new_capacity):
                new_spot = ParkingSpot(lot_id=lot.id, status="available")
                db.session.add(new_spot)
            db.session.commit()
        elif new_capacity < old_capacity:
            # Remove available spots (do not remove booked spots)
            spots_to_remove = ParkingSpot.query.filter_by(lot_id=lot.id, status="available").limit(old_capacity - new_capacity).all()
            for spot in spots_to_remove:
                db.session.delete(spot)
            db.session.commit()

        flash('✅ Parking lot updated.')
        return redirect('/admin/dashboard')

    return render_template('edit_lot.html', lot=lot)

#  Delete Parking Lot (Only if Empty)
@app.route('/admin/delete_lot/<int:lot_id>', methods=['POST'])
def delete_lot(lot_id):
    if session.get("role") != "admin":
        flash("Unauthorized access.")
        return redirect("/login")

    lot = ParkingLot.query.get_or_404(lot_id)
    booked_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='booked').count()  # fixed: use 'booked'

    if booked_spots > 0:
        flash("❌ Cannot delete. Spots are still booked.")
    else:
        ParkingSpot.query.filter_by(lot_id=lot.id).delete()
        db.session.delete(lot)
        db.session.commit()
        flash("✅ Parking lot deleted.")

    return redirect('/admin/dashboard')

 #User Dashboard
@app.route("/user/dashboard")
def user_dashboard():
    if session.get("role") != "user":
        flash("Access denied: Users only.")
        return redirect("/login")

    search = request.args.get('search', '').strip()
    if search:
        lots = ParkingLot.query.filter(
            (ParkingLot.lot_name.ilike(f'%{search}%')) |
            (ParkingLot.address.ilike(f'%{search}%')) |
            (ParkingLot.pincode.ilike(f'%{search}%')) |
            (ParkingLot.city.ilike(f'%{search}%'))
        ).all()
    else:
        lots = ParkingLot.query.all()

    lot_info = []
    for lot in lots:
        empty_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status="available").count()
        lot_info.append({
            "id": lot.id,
            "lot_name": lot.lot_name,
            "address": lot.address,
            "city": lot.city,
            "pincode": lot.pincode,
            "capacity": lot.capacity,
            "empty_spots": empty_spots,
            "price": lot.price
        })

    user_id = session.get("user_id")
    current_reservations = []
    past_reservations = []
    if user_id:
        all_reservations = Reservation.query.filter_by(user_id=user_id).all()
        for res in all_reservations:
            # No need to calculate per-lot spot number, just use spot.id
            if res.leaving_timestamp is None:
                current_reservations.append(res)
            else:
                past_reservations.append(res)
    else:
        print("[DEBUG] user_id is None, no reservations fetched")

    #  data prep for  charts
    import calendar
    from collections import defaultdict
    monthly_usage = defaultdict(int)
    monthly_spent = defaultdict(float)
    for res in past_reservations:
        if res.leaving_timestamp:
            month = res.leaving_timestamp.strftime('%b %Y')
            monthly_usage[month] += 1
            monthly_spent[month] += res.total_cost if res.total_cost else 0
    chart_labels = list(monthly_usage.keys())
    chart_usage = [monthly_usage[m] for m in chart_labels]
    chart_spent = [monthly_spent[m] for m in chart_labels]
    return render_template("user_dashboard.html", username=session.get("username", "Guest"), lots=lot_info, current_reservations=current_reservations, past_reservations=past_reservations, chart_labels=chart_labels, chart_usage=chart_usage, chart_spent=chart_spent)
# View All Spots in a Lot (Admin)
@app.route("/admin/lot/<int:lot_id>/spots")
def view_spots(lot_id):
    if session.get("role") != "admin":
        flash("Unauthorized access.")
        return redirect("/login")

    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    return render_template("view_spots.html", lot=lot, spots=spots)

#  Delete Spot (if Empty)
@app.route('/admin/delete_spot/<int:spot_id>', methods=['POST'])
def delete_spot(spot_id):
    if session.get("role") != "admin":
        flash("Unauthorized access.")
        return redirect("/login")

    spot = ParkingSpot.query.get_or_404(spot_id)

    if spot.status == "available":  # fixed: use 'available'
        db.session.delete(spot)
        db.session.commit()
        flash("✅ Spot deleted successfully.")
    else:
        flash("❌ Cannot delete booked spot.")

    return redirect(f"/admin/lot/{spot.lot_id}/spots")

@app.route('/reserve/<int:lot_id>', methods=['POST'])
def reserve_spot(lot_id):
    if session.get("role") != "user":
        flash("Unauthorized access.")
        return redirect("/login")

    # Get all available spots in this lot, ordered by ID
    available_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='available').order_by(ParkingSpot.id.asc()).all()
    if available_spots:
        # The per-lot spot number is the index in this list + 1
        spot = available_spots[0]
        spot.status = "booked"
        # Calculate spot_number for this reservation
        spot_number = 1  # always the first available
        reservation = Reservation(
            spot_id=spot.id,
            user_id=session.get("user_id")
        )
        db.session.add(reservation)
        db.session.commit()
        flash(f"✅ Spot {spot_number} reserved successfully.")
    else:
        flash("❌ No empty spots available.")

    return redirect("/user/dashboard")

@app.route('/release/<int:reservation_id>', methods=['POST'])
def release_spot(reservation_id):
    if session.get("role") != "user":
        flash("Unauthorized access.")
        return redirect("/login")

    reservation = Reservation.query.get(reservation_id)
    if reservation and reservation.user_id == session.get("user_id"):
        spot = ParkingSpot.query.get(reservation.spot_id)
        if spot:
            spot.status = "available"
            # Calculate total time and save leaving_timestamp
            from datetime import datetime
            reservation.leaving_timestamp = datetime.utcnow()
            duration = (reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 60  # minutes
            # Cost calculation: ₹100 per hour (rounded up)
            cost_per_hour = 100.0
            hours = duration / 60
            total_cost = round(cost_per_hour * (hours if hours > 0 else 1), 2)
            reservation.total_cost = total_cost
            db.session.commit()
            # Do NOT delete reservation, keep for history
            flash(f"✅ Spot released successfully. Total time parked: {duration:.2f} minutes. Please pay ₹{total_cost:.2f}.")
        else:
            flash("❌ Spot not found.")
    else:
        flash("❌ Reservation not found or unauthorized.")

    return redirect("/user/dashboard")

@app.route('/reserve/<int:lot_id>')
def reserve(lot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    empty_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='available').count()
    spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()

    return render_template('reserve.html', lot=lot, empty_spots=empty_spots, spots=spots)

# @app.route('/confirm_reservation/<int:lot_id>', methods=['POST'])
# def confirm_reservation(lot_id):
#     if 'user_id' not in session:
#         return redirect(url_for('login'))

#     spot_id = request.form.get("spot_id")
#     if spot_id:
#         if spot_id == "first_available":
#             spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='available').first()
#         else:
#             spot = ParkingSpot.query.filter_by(id=spot_id, lot_id=lot_id, status='available').first()
#     else:
#         flash("❌ No spot selected.")
#         return redirect(url_for('reserve', lot_id=lot_id))

#     if spot:
#         spot.status = 'booked'
#         spot.booked_by = session.get("username")
#         reservation = Reservation(
#             spot_id=spot.id,
#             user_id=session.get("user_id")
#         )
#         db.session.add(reservation)
#         db.session.commit()
#         flash(f"✅ Spot {spot.id} reserved successfully!")
#     else:
#         flash("❌ Spot is no longer available.")

#     return redirect(url_for('user_dashboard'))


@app.route('/admin_charts')
def admin_charts():
    # Prepare summary data for charts
    parking_lots = ParkingLot.query.all()
    users = User.query.all()
    reservations = Reservation.query.all()
    from collections import defaultdict
    import calendar
    # Monthly Revenue per Parking Lot
    monthly_lot_revenue = defaultdict(lambda: defaultdict(float))
    # Monthly New User Registrations
    monthly_new_users = defaultdict(int)
    # Most Frequently Used Parking Lots
    lot_usage_counts = defaultdict(int)
    # Total Reservations per City
    city_res_counts = defaultdict(int)
    # Daily/Hourly Usage Pattern
    hourly_usage = defaultdict(int)
    daily_usage = defaultdict(int)
    # Prepare lot names
    lot_names = [lot.lot_name for lot in parking_lots]
    lot_chart_labels = lot_names
    lot_chart_data = []
    # Monthly revenue per lot
    for res in reservations:
        if res.spot and res.spot.lot:
            lot_name = res.spot.lot.lot_name
            city = res.spot.lot.city if res.spot.lot.city else "Unknown"
            if res.leaving_timestamp and res.total_cost:
                month = res.leaving_timestamp.strftime('%b %Y')
                monthly_lot_revenue[lot_name][month] += res.total_cost
            lot_usage_counts[lot_name] += 1
            city_res_counts[city] += 1
        # Daily/Hourly usage
        if res.parking_timestamp:
            day = res.parking_timestamp.strftime('%Y-%m-%d')
            hour = res.parking_timestamp.hour
            daily_usage[day] += 1
            hourly_usage[hour] += 1
    # Monthly new user registrations
    for user in users:
        if user.role == 'user' and hasattr(user, 'created_at') and user.created_at:
            month = user.created_at.strftime('%b %Y')
            monthly_new_users[month] += 1
    # Prepare chart data
    # 1. Monthly Revenue per Parking Lot (bar chart per lot)
    monthly_labels = sorted({m for lot in monthly_lot_revenue.values() for m in lot.keys()})
    lot_monthly_revenue_data = {lot: [monthly_lot_revenue[lot][m] if m in monthly_lot_revenue[lot] else 0 for m in monthly_labels] for lot in lot_names}
    # 4. Monthly New User Registrations
    new_user_months = sorted(monthly_new_users.keys())
    new_user_counts = [monthly_new_users[m] for m in new_user_months]
    # 5. Most Frequently Used Parking Lots
    most_used_lot_labels = list(lot_usage_counts.keys())
    most_used_lot_data = [lot_usage_counts[k] for k in most_used_lot_labels]
    # 6. Total Reservations per City
    city_labels = list(city_res_counts.keys())
    city_data = [city_res_counts[k] for k in city_labels]
    # 7. Daily/Hourly Usage Pattern
    hourly_labels = [str(h) for h in range(24)]
    hourly_data = [hourly_usage[h] if h in hourly_usage else 0 for h in range(24)]
    daily_labels = sorted(daily_usage.keys())
    daily_data = [daily_usage[d] for d in daily_labels]
    # Existing summary
    lot_res_counts = defaultdict(int)
    for res in reservations:
        if res.spot and res.spot.lot:
            lot_res_counts[res.spot.lot.lot_name] += 1
    lot_chart_data = [lot_res_counts[name] for name in lot_chart_labels]
    total_revenue = sum(res.total_cost for res in reservations if res.total_cost)
    active_users = len(set(res.user_id for res in reservations if res.leaving_timestamp is None))
    total_users = len([u for u in users if u.role == 'user'])
    return render_template('admin_charts.html',
        lot_chart_labels=lot_chart_labels,
        lot_chart_data=lot_chart_data,
        total_revenue=total_revenue,
        active_users=active_users,
        total_users=total_users,
        monthly_labels=monthly_labels,
        lot_monthly_revenue_data=lot_monthly_revenue_data,
        new_user_months=new_user_months,
        new_user_counts=new_user_counts,
        most_used_lot_labels=most_used_lot_labels,
        most_used_lot_data=most_used_lot_data,
        city_labels=city_labels,
        city_data=city_data,
        hourly_labels=hourly_labels,
        hourly_data=hourly_data,
        daily_labels=daily_labels,
        daily_data=daily_data
    )

# Move user_charts route to the end to avoid shadowing or context issues
@app.route('/user_charts')
def user_charts():
    user_id = session.get("user_id")
    past_reservations = []
    active_count = 0
    completed_count = 0
    lot_pref_counts = {}
    monthly_usage = {}
    monthly_spent = {}
    monthly_avg_duration = {}
    if user_id:
        all_reservations = Reservation.query.filter_by(user_id=user_id).all()
        from collections import defaultdict
        monthly_usage = defaultdict(int)
        monthly_spent = defaultdict(float)
        monthly_total_duration = defaultdict(float)
        monthly_count = defaultdict(int)
        lot_pref_counts = defaultdict(int)
        for res in all_reservations:
            if res.leaving_timestamp is not None:
                past_reservations.append(res)
                month = res.leaving_timestamp.strftime('%b %Y')
                monthly_usage[month] += 1
                monthly_spent[month] += res.total_cost if res.total_cost else 0
                if res.parking_timestamp and res.leaving_timestamp:
                    duration = (res.leaving_timestamp - res.parking_timestamp).total_seconds() / 60  # minutes
                    monthly_total_duration[month] += duration
                    monthly_count[month] += 1
                if res.spot and res.spot.lot:
                    lot_pref_counts[res.spot.lot.lot_name] += 1
                completed_count += 1
            else:
                active_count += 1
        chart_labels = list(monthly_usage.keys())
        chart_usage = [monthly_usage[m] for m in chart_labels]
        chart_spent = [monthly_spent[m] for m in chart_labels]
        chart_avg_duration = [round(monthly_total_duration[m]/monthly_count[m],2) if monthly_count[m]>0 else 0 for m in chart_labels]
        lot_pref_labels = list(lot_pref_counts.keys())
        lot_pref_data = [lot_pref_counts[k] for k in lot_pref_labels]
    else:
        chart_labels = []
        chart_usage = []
        chart_spent = []
        chart_avg_duration = []
        lot_pref_labels = []
        lot_pref_data = []
    # Reservation status breakdown
    status_labels = ["Active", "Completed"]
    status_data = [active_count, completed_count]
    return render_template('user_charts.html',
        chart_labels=chart_labels,
        chart_usage=chart_usage,
        chart_spent=chart_spent,
        chart_avg_duration=chart_avg_duration,
        status_labels=status_labels,
        status_data=status_data,
        lot_pref_labels=lot_pref_labels,
        lot_pref_data=lot_pref_data
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        initialize_admin()
    app.run(debug=True)