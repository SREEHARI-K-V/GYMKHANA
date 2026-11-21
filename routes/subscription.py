import secrets
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.database import query_db, execute_db
from utils.auth import login_required, role_required
from utils.helpers import calculate_remaining_days, log_activity, send_notification

subscription_bp = Blueprint('subscription', __name__, url_prefix='/subscription')

@subscription_bp.route('/plans')
def plans():
    active_plans = query_db("SELECT * FROM membership_plans WHERE status = 'active' ORDER BY price ASC")
    return render_template('member/membership_plans.html', plans=active_plans)

@subscription_bp.route('/my-membership')
@login_required
@role_required('MEMBER')
def my_membership():
    member_id = session.get('user_id')
    
    # Fetch active or latest subscription
    subscription = query_db(
        """SELECT s.*, p.name as plan_name, p.description as plan_description, p.duration_months, p.benefits, p.price as plan_price
           FROM subscriptions s
           JOIN membership_plans p ON s.plan_id = p.id
           WHERE s.member_id = %s
           ORDER BY s.id DESC LIMIT 1""",
        (member_id,), one=True
    )
    
    status_label = "No Active Subscription"
    remaining_days = 0
    progress_percentage = 0
    
    if subscription:
        remaining_days = calculate_remaining_days(subscription['expiry_date'])
        
        if remaining_days <= 0:
            status_label = "Expired"
            if subscription['status'] != 'expired':
                execute_db("UPDATE subscriptions SET status = 'expired' WHERE id = %s", (subscription['id'],))
                subscription['status'] = 'expired'
            progress_percentage = 0
        elif remaining_days <= 7:
            status_label = "Expiring Soon"
            total_duration_days = max(1, subscription['duration_months'] * 30)
            progress_percentage = min(100, max(0, round((remaining_days / total_duration_days) * 100)))
        else:
            status_label = "Active"
            total_duration_days = max(1, subscription['duration_months'] * 30)
            progress_percentage = min(100, max(0, round((remaining_days / total_duration_days) * 100)))

    # Fetch available plans for subscribe / upgrade / renewal
    available_plans = query_db("SELECT * FROM membership_plans WHERE status = 'active' ORDER BY price ASC")
    
    # Fetch subscription history
    history = query_db(
        """SELECT sh.*, p.name as plan_name
           FROM subscription_history sh
           JOIN membership_plans p ON sh.plan_id = p.id
           WHERE sh.member_id = %s
           ORDER BY sh.date DESC""",
        (member_id,)
    )

    # Fetch recent payments for quick display
    recent_payments = query_db(
        """SELECT p.*, mp.name as plan_name
           FROM payments p
           JOIN membership_plans mp ON p.plan_id = mp.id
           WHERE p.member_id = %s
           ORDER BY p.payment_date DESC LIMIT 5""",
        (member_id,)
    )

    return render_template(
        'member/membership.html', 
        subscription=subscription, 
        remaining_days=remaining_days,
        status_label=status_label,
        progress_percentage=progress_percentage,
        available_plans=available_plans,
        history=history,
        recent_payments=recent_payments
    )

@subscription_bp.route('/checkout/<int:plan_id>')
@login_required
@role_required('MEMBER')
def checkout(plan_id):
    """Online Payment Checkout Gateway Page for Membership Subscription & Renewal."""
    member_id = session.get('user_id')
    user = query_db("SELECT * FROM users WHERE id = %s", (member_id,), one=True)
    plan = query_db("SELECT * FROM membership_plans WHERE id = %s AND status = 'active'", (plan_id,), one=True)
    
    if not plan:
        flash('Selected membership plan is not available.', 'danger')
        return redirect(url_for('subscription.my_membership'))

    # Check existing subscription for renewal calculation
    active_sub = query_db(
        """SELECT * FROM subscriptions 
           WHERE member_id = %s AND status = 'active' 
           ORDER BY id DESC LIMIT 1""",
        (member_id,), one=True
    )

    is_renewal = False
    current_expiry = None
    new_expiry = None

    if active_sub:
        try:
            exp_date = datetime.strptime(str(active_sub['expiry_date']), '%Y-%m-%d').date()
        except Exception:
            exp_date = active_sub['expiry_date']

        if exp_date >= date.today():
            is_renewal = True
            current_expiry = exp_date
            new_expiry = current_expiry + relativedelta(months=plan['duration_months'])
        else:
            new_expiry = date.today() + relativedelta(months=plan['duration_months'])
    else:
        new_expiry = date.today() + relativedelta(months=plan['duration_months'])

    base_amount = float(plan['price'])
    # Optional tax breakdown (or inclusive)
    gst_amount = round(base_amount * 0.18, 2)
    total_payable = round(base_amount + gst_amount, 2)

    return render_template(
        'member/checkout.html',
        user=user,
        plan=plan,
        is_renewal=is_renewal,
        current_expiry=current_expiry,
        new_expiry=new_expiry,
        base_amount=base_amount,
        gst_amount=gst_amount,
        total_payable=total_payable
    )

@subscription_bp.route('/process-payment', methods=['POST'])
@login_required
@role_required('MEMBER')
def process_payment():
    """Processes online payment, registers payment transaction, activates/renews membership."""
    member_id = session.get('user_id')
    plan_id = request.form.get('plan_id', type=int)
    payment_method = request.form.get('payment_method', 'UPI').strip()
    
    if not plan_id:
        flash('Invalid plan selected.', 'danger')
        return redirect(url_for('subscription.my_membership'))

    plan = query_db("SELECT * FROM membership_plans WHERE id = %s AND status = 'active'", (plan_id,), one=True)
    if not plan:
        flash('Selected membership plan is no longer available.', 'danger')
        return redirect(url_for('subscription.my_membership'))

    # Calculate dates & check renewal status
    active_sub = query_db(
        """SELECT * FROM subscriptions 
           WHERE member_id = %s AND status = 'active' 
           ORDER BY id DESC LIMIT 1""",
        (member_id,), one=True
    )

    start_d = date.today()
    is_renewal = False

    if active_sub:
        try:
            exp_date = datetime.strptime(str(active_sub['expiry_date']), '%Y-%m-%d').date()
        except Exception:
            exp_date = active_sub['expiry_date']

        if exp_date >= date.today():
            is_renewal = True
            # Intelligent renewal extends from existing expiry so no days are lost!
            expiry_d = exp_date + relativedelta(months=plan['duration_months'])
            execute_db("UPDATE subscriptions SET status = 'renewed' WHERE id = %s", (active_sub['id'],))
        else:
            expiry_d = start_d + relativedelta(months=plan['duration_months'])
            execute_db("UPDATE subscriptions SET status = 'expired' WHERE id = %s", (active_sub['id'],))
    else:
        expiry_d = start_d + relativedelta(months=plan['duration_months'])

    payment_type = 'RENEWAL' if is_renewal else 'NEW_SUBSCRIPTION'

    # Insert new subscription
    sub_id = execute_db(
        """INSERT INTO subscriptions (member_id, plan_id, start_date, expiry_date, amount, status)
           VALUES (%s, %s, %s, %s, %s, 'active')""",
        (member_id, plan['id'], start_d, expiry_d, plan['price'])
    )

    # Generate unique transaction reference & receipt number
    date_code = datetime.now().strftime('%Y%m%d%H%M')
    rand_hex = secrets.token_hex(3).upper()
    transaction_id = f"TXN-GYM-{date_code}-{rand_hex}"
    receipt_number = f"REC-{datetime.now().strftime('%Y%m')}-{secrets.randbelow(90000) + 10000}"

    # Insert payment record into payments table
    payment_id = execute_db(
        """INSERT INTO payments (member_id, subscription_id, plan_id, amount, payment_method, transaction_id, payment_type, payment_status, receipt_number, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'COMPLETED', %s, %s)""",
        (member_id, sub_id, plan['id'], plan['price'], payment_method, transaction_id, payment_type, receipt_number, f"Online payment via {payment_method}")
    )

    # Insert history log
    execute_db(
        """INSERT INTO subscription_history (subscription_id, member_id, plan_id, action, amount)
           VALUES (%s, %s, %s, %s, %s)""",
        (sub_id, member_id, plan['id'], payment_type, plan['price'])
    )

    action_label = "Renewed" if is_renewal else "Subscribed to"
    log_activity(member_id, 'MEMBER', f'PAYMENT_{payment_type}', f"Paid ₹{plan['price']} via {payment_method} ({transaction_id}) for {plan['name']}")

    send_notification(
        member_id, 
        f"Payment Successful & Membership { 'Renewed' if is_renewal else 'Activated' }!", 
        f"Your payment of ₹{plan['price']} via {payment_method} was successful (Ref: {transaction_id}). Valid until {expiry_d.strftime('%b %d, %Y')}.",
        "success"
    )

    flash(f"Payment successful! You {action_label} {plan['name']}. Valid until {expiry_d.strftime('%b %d, %Y')}.", 'success')
    return redirect(url_for('subscription.receipt', payment_id=payment_id))

@subscription_bp.route('/payments')
@login_required
@role_required('MEMBER')
def payment_history():
    """Member can review all payment transactions and download invoices."""
    member_id = session.get('user_id')
    
    payments = query_db(
        """SELECT p.*, mp.name as plan_name, mp.duration_months
           FROM payments p
           JOIN membership_plans mp ON p.plan_id = mp.id
           WHERE p.member_id = %s
           ORDER BY p.payment_date DESC""",
        (member_id,)
    )

    total_spent = sum(p['amount'] for p in payments if p['payment_status'] == 'COMPLETED')

    return render_template(
        'member/payment_history.html',
        payments=payments,
        total_spent=total_spent
    )

@subscription_bp.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    """View and print Tax Invoice / Payment Receipt."""
    user_id = session.get('user_id')
    user_role = session.get('user_role', 'MEMBER').upper()

    payment = query_db(
        """SELECT p.*, u.name as member_name, u.email as member_email, u.phone as member_phone,
                  mp.name as plan_name, mp.duration_months, mp.description as plan_description,
                  s.start_date, s.expiry_date
           FROM payments p
           JOIN users u ON p.member_id = u.id
           JOIN membership_plans mp ON p.plan_id = mp.id
           LEFT JOIN subscriptions s ON p.subscription_id = s.id
           WHERE p.id = %s""",
        (payment_id,), one=True
    )

    if not payment:
        flash('Receipt not found.', 'danger')
        return redirect(url_for('subscription.my_membership'))

    # Security check: member can only view their own receipt, admin can view any receipt
    if user_role == 'MEMBER' and payment['member_id'] != user_id:
        flash('Unauthorized access to receipt.', 'danger')
        return redirect(url_for('subscription.my_membership'))

    return render_template('member/receipt.html', payment=payment)
