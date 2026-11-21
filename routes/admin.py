from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.database import query_db, execute_db
from utils.auth import login_required, role_required
from utils.auth import hash_password
from utils.helpers import log_activity, send_notification

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@role_required('ADMIN')
def dashboard():
    # KPI Stats from Database
    total_members = query_db(
        "SELECT COUNT(*) as cnt FROM users u JOIN roles r ON u.role_id = r.id WHERE LOWER(r.name) = 'member'",
        one=True
    )['cnt']

    total_trainers = query_db(
        "SELECT COUNT(*) as cnt FROM users u JOIN roles r ON u.role_id = r.id WHERE LOWER(r.name) = 'trainer'",
        one=True
    )['cnt']

    active_subs = query_db("SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active'", one=True)['cnt']
    expired_subs = query_db("SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'expired'", one=True)['cnt']
    
    from datetime import date, timedelta
    today_str = date.today().strftime('%Y-%m-%d')
    next_week_str = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')

    expiring_soon = query_db(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active' AND expiry_date >= %s AND expiry_date <= %s",
        (today_str, next_week_str),
        one=True
    )['cnt']

    total_branches = query_db("SELECT COUNT(*) as cnt FROM gym_branches", one=True)['cnt']
    
    total_revenue_res = query_db("SELECT SUM(amount) as total FROM subscriptions", one=True)
    total_revenue = float(total_revenue_res['total']) if total_revenue_res and total_revenue_res['total'] else 0.0

    recent_users = query_db(
        """SELECT u.*, r.name as role_name 
           FROM users u 
           JOIN roles r ON u.role_id = r.id 
           ORDER BY u.id DESC LIMIT 5"""
    )

    recent_subscriptions = query_db(
        """SELECT s.*, u.name as member_name, p.name as plan_name 
           FROM subscriptions s 
           JOIN users u ON s.member_id = u.id 
           JOIN membership_plans p ON s.plan_id = p.id 
           ORDER BY s.id DESC LIMIT 5"""
    )

    total_online_payments_res = query_db("SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total FROM payments WHERE payment_status = 'COMPLETED'", one=True)
    total_online_payments = total_online_payments_res['cnt'] if total_online_payments_res else 0
    total_online_revenue = float(total_online_payments_res['total']) if total_online_payments_res else 0.0

    pending_reviews_count = query_db("SELECT COUNT(*) as cnt FROM reviews WHERE status = 'pending'", one=True)['cnt']

    return render_template(
        'admin/dashboard.html',
        total_members=total_members,
        total_trainers=total_trainers,
        active_subs=active_subs,
        expired_subs=expired_subs,
        expiring_soon=expiring_soon,
        total_branches=total_branches,
        total_revenue=total_revenue,
        total_online_payments=total_online_payments,
        total_online_revenue=total_online_revenue,
        pending_reviews_count=pending_reviews_count,
        recent_users=recent_users,
        recent_subscriptions=recent_subscriptions
    )

# Users Management
@admin_bp.route('/users')
@login_required
@role_required('ADMIN')
def users():
    search = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()
    
    query = """SELECT u.*, r.name as role_name 
               FROM users u 
               JOIN roles r ON u.role_id = r.id 
               WHERE 1=1"""
    params = []

    if search:
        query += " AND (LOWER(u.name) LIKE %s OR LOWER(u.email) LIKE %s OR u.phone LIKE %s)"
        sp = f"%{search.lower()}%"
        params.extend([sp, sp, sp])

    if role_filter:
        query += " AND LOWER(r.name) = %s"
        params.append(role_filter.lower())

    query += " ORDER BY u.id DESC"
    user_list = query_db(query, tuple(params))
    roles = query_db("SELECT * FROM roles ORDER BY id ASC")

    return render_template('admin/users.html', user_list=user_list, roles=roles, search=search, role_filter=role_filter)

@admin_bp.route('/users/toggle-status/<int:user_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_user_status(user_id):
    user = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.users'))

    new_status = 'inactive' if user['status'] == 'active' else 'active'
    execute_db("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))

    log_activity(session.get('user_id'), 'ADMIN', 'USER_STATUS_CHANGE', f"Changed status of user '{user['email']}' to {new_status}")
    flash(f"Status for user {user['name']} updated to {new_status}.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_user(user_id):
    user = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.users'))

    if user['id'] == session.get('user_id'):
        flash('You cannot delete your own admin account.', 'danger')
        return redirect(url_for('admin.users'))

    execute_db("DELETE FROM users WHERE id = %s", (user_id,))
    log_activity(session.get('user_id'), 'ADMIN', 'USER_DELETED', f"Deleted user '{user['email']}' (ID #{user_id})")
    flash(f"User {user['name']} has been deleted.", 'info')
    return redirect(url_for('admin.users'))

# Trainers Management
@admin_bp.route('/trainers', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def trainers():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        specialization = request.form.get('specialization', '').strip()
        experience = request.form.get('experience', '').strip()
        qualification = request.form.get('qualification', '').strip()

        if not name or not email or not password:
            flash('Name, Email, and Password are required for trainer creation.', 'danger')
            return redirect(url_for('admin.trainers'))

        existing = query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
        if existing:
            flash('A user with this email address already exists.', 'danger')
            return redirect(url_for('admin.trainers'))

        trainer_role = query_db("SELECT id FROM roles WHERE LOWER(name) = 'trainer'", one=True)
        role_id = trainer_role['id'] if trainer_role else 2

        user_id = execute_db(
            """INSERT INTO users (role_id, name, email, password_hash, phone, status)
               VALUES (%s, %s, %s, %s, %s, 'active')""",
            (role_id, name, email, hash_password(password), phone)
        )

        execute_db(
            """INSERT INTO trainers (user_id, specialization, experience, qualification, status)
               VALUES (%s, %s, %s, %s, 'active')""",
            (user_id, specialization, experience, qualification)
        )

        log_activity(session.get('user_id'), 'ADMIN', 'TRAINER_CREATED', f"Created trainer '{name}' ({email})")
        flash(f"Trainer '{name}' created successfully!", 'success')
        return redirect(url_for('admin.trainers'))

    trainer_list = query_db(
        """SELECT t.*, u.name, u.email, u.phone, u.status as user_status,
                  (SELECT COUNT(*) FROM workout_plans wp WHERE wp.trainer_id = u.id AND wp.status = 'active') as active_assigned_members
           FROM trainers t
           JOIN users u ON t.user_id = u.id
           ORDER BY t.id DESC"""
    )

    return render_template('admin/trainers.html', trainer_list=trainer_list)

# Membership Plans Management
@admin_bp.route('/plans', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def plans():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        duration_months = request.form.get('duration_months', type=int)
        price = request.form.get('price', type=float)
        benefits = request.form.get('benefits', '').strip()

        if not name or not duration_months or not price:
            flash('Plan name, duration, and price are required.', 'danger')
            return redirect(url_for('admin.plans'))

        execute_db(
            """INSERT INTO membership_plans (name, description, duration_months, price, benefits, status)
               VALUES (%s, %s, %s, %s, %s, 'active')""",
            (name, description, duration_months, price, benefits)
        )

        log_activity(session.get('user_id'), 'ADMIN', 'PLAN_CREATED', f"Created plan '{name}' (₹{price})")
        flash(f"Membership plan '{name}' created successfully!", 'success')
        return redirect(url_for('admin.plans'))

    plan_list = query_db("SELECT * FROM membership_plans ORDER BY price ASC")
    return render_template('admin/plans.html', plan_list=plan_list)

@admin_bp.route('/plans/toggle/<int:plan_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def toggle_plan(plan_id):
    plan = query_db("SELECT * FROM membership_plans WHERE id = %s", (plan_id,), one=True)
    if plan:
        new_status = 'inactive' if plan['status'] == 'active' else 'active'
        execute_db("UPDATE membership_plans SET status = %s WHERE id = %s", (new_status, plan_id))
        flash(f"Plan '{plan['name']}' status updated to {new_status}.", 'info')
    return redirect(url_for('admin.plans'))

# Subscriptions List
@admin_bp.route('/subscriptions')
@login_required
@role_required('ADMIN')
def subscriptions():
    subs = query_db(
        """SELECT s.*, u.name as member_name, u.email as member_email, p.name as plan_name
           FROM subscriptions s
           JOIN users u ON s.member_id = u.id
           JOIN membership_plans p ON s.plan_id = p.id
           ORDER BY s.id DESC"""
    )
    return render_template('admin/subscriptions.html', subscriptions=subs)

# Gym Branch Management
@admin_bp.route('/branches', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def branches():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        opening_hours = request.form.get('opening_hours', '').strip()
        facilities = request.form.get('facilities', '').strip()
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)

        if not name or not address or not latitude or not longitude:
            flash('Branch name, address, latitude, and longitude are required.', 'danger')
            return redirect(url_for('admin.branches'))

        execute_db(
            """INSERT INTO gym_branches (name, address, phone, opening_hours, facilities, latitude, longitude, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')""",
            (name, address, phone, opening_hours, facilities, latitude, longitude)
        )

        log_activity(session.get('user_id'), 'ADMIN', 'BRANCH_CREATED', f"Created gym branch '{name}'")
        flash(f"Gym branch '{name}' created successfully!", 'success')
        return redirect(url_for('admin.branches'))

    branch_list = query_db("SELECT * FROM gym_branches ORDER BY name ASC")
    return render_template('admin/branches.html', branch_list=branch_list)

@admin_bp.route('/branches/delete/<int:branch_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_branch(branch_id):
    execute_db("DELETE FROM gym_branches WHERE id = %s", (branch_id,))
    flash('Branch deleted successfully.', 'info')
    return redirect(url_for('admin.branches'))

# Activity Logs
@admin_bp.route('/activity-logs')
@login_required
@role_required('ADMIN')
def activity_logs():
    logs = query_db(
        """SELECT l.*, u.name as user_name, u.email as user_email
           FROM activity_logs l
           LEFT JOIN users u ON l.user_id = u.id
           ORDER BY l.created_at DESC LIMIT 100"""
    )
    return render_template('admin/activity_logs.html', logs=logs)

# Reviews & Feedback Moderation
@admin_bp.route('/reviews')
@login_required
@role_required('ADMIN')
def reviews():
    status_filter = request.args.get('status', 'all').strip()
    type_filter = request.args.get('type', 'all').strip()

    sql = """SELECT r.*, u.name as user_name, u.email as user_email, ro.name as user_role,
                    t.name as trainer_name
             FROM reviews r
             JOIN users u ON r.user_id = u.id
             JOIN roles ro ON u.role_id = ro.id
             LEFT JOIN users t ON r.trainer_id = t.id
             WHERE 1=1"""
    params = []

    if status_filter != 'all':
        sql += " AND r.status = %s"
        params.append(status_filter)

    if type_filter != 'all':
        sql += " AND r.review_type = %s"
        params.append(type_filter)

    sql += " ORDER BY r.created_at DESC"

    reviews_list = query_db(sql, tuple(params))

    # Counters
    total_reviews = query_db("SELECT COUNT(*) as cnt FROM reviews", one=True)['cnt']
    pending_count = query_db("SELECT COUNT(*) as cnt FROM reviews WHERE status = 'pending'", one=True)['cnt']
    approved_count = query_db("SELECT COUNT(*) as cnt FROM reviews WHERE status = 'approved'", one=True)['cnt']
    rejected_count = query_db("SELECT COUNT(*) as cnt FROM reviews WHERE status = 'rejected'", one=True)['cnt']

    return render_template(
        'admin/reviews.html',
        reviews_list=reviews_list,
        current_status=status_filter,
        current_type=type_filter,
        total_reviews=total_reviews,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count
    )

@admin_bp.route('/reviews/<int:review_id>/approve', methods=['POST'])
@login_required
@role_required('ADMIN')
def approve_review(review_id):
    review = query_db("SELECT * FROM reviews WHERE id = %s", (review_id,), one=True)
    if not review:
        flash('Review not found.', 'danger')
        return redirect(url_for('admin.reviews'))

    execute_db("UPDATE reviews SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (review_id,))
    log_activity(session.get('user_id'), 'ADMIN', 'REVIEW_APPROVED', f"Approved review ID #{review_id}")
    
    send_notification(
        review['user_id'],
        "Review Approved!",
        "Your submitted review has been approved and published by the administrator. Thank you for your feedback!",
        "success"
    )

    flash('Review has been approved and published successfully!', 'success')
    return redirect(url_for('admin.reviews'))

@admin_bp.route('/reviews/<int:review_id>/reject', methods=['POST'])
@login_required
@role_required('ADMIN')
def reject_review(review_id):
    review = query_db("SELECT * FROM reviews WHERE id = %s", (review_id,), one=True)
    if not review:
        flash('Review not found.', 'danger')
        return redirect(url_for('admin.reviews'))

    execute_db("UPDATE reviews SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (review_id,))
    log_activity(session.get('user_id'), 'ADMIN', 'REVIEW_REJECTED', f"Rejected review ID #{review_id}")

    send_notification(
        review['user_id'],
        "Review Status Update",
        "Your submitted review was declined by the administrator. Please ensure content complies with community guidelines.",
        "warning"
    )

    flash('Review has been rejected.', 'warning')
    return redirect(url_for('admin.reviews'))

@admin_bp.route('/reviews/<int:review_id>/delete', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_review(review_id):
    execute_db("DELETE FROM reviews WHERE id = %s", (review_id,))
    log_activity(session.get('user_id'), 'ADMIN', 'REVIEW_DELETED', f"Deleted review ID #{review_id}")
    flash('Review deleted permanently.', 'info')
    return redirect(url_for('admin.reviews'))

# Online Payments Management
@admin_bp.route('/payments')
@login_required
@role_required('ADMIN')
def payments():
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all').strip()

    sql = """SELECT p.*, u.name as member_name, u.email as member_email, mp.name as plan_name
             FROM payments p
             JOIN users u ON p.member_id = u.id
             JOIN membership_plans mp ON p.plan_id = mp.id
             WHERE 1=1"""
    params = []

    if search:
        sql += " AND (u.name LIKE %s OR u.email LIKE %s OR p.transaction_id LIKE %s OR p.receipt_number LIKE %s)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern, pattern])

    if status_filter != 'all':
        sql += " AND p.payment_status = %s"
        params.append(status_filter)

    sql += " ORDER BY p.payment_date DESC"

    payments_list = query_db(sql, tuple(params))

    # Payment statistics
    total_revenue_res = query_db("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE payment_status = 'COMPLETED'", one=True)
    total_revenue = float(total_revenue_res['total']) if total_revenue_res else 0.0
    total_txns = query_db("SELECT COUNT(*) as cnt FROM payments", one=True)['cnt']
    upi_count = query_db("SELECT COUNT(*) as cnt FROM payments WHERE payment_method = 'UPI'", one=True)['cnt']
    card_count = query_db("SELECT COUNT(*) as cnt FROM payments WHERE payment_method LIKE '%Card%'", one=True)['cnt']

    return render_template(
        'admin/payments.html',
        payments=payments_list,
        search=search,
        status_filter=status_filter,
        total_revenue=total_revenue,
        total_txns=total_txns,
        upi_count=upi_count,
        card_count=card_count
    )

