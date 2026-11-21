from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.database import query_db, execute_db
from utils.auth import login_required, role_required
from utils.helpers import log_activity, send_notification

review_bp = Blueprint('review', __name__, url_prefix='/review')

@review_bp.route('/my-feedback')
@login_required
def my_feedback():
    """Page where members and trainers can submit reviews and view their submission statuses."""
    user_id = session.get('user_id')
    user_role = session.get('user_role', '').upper()

    # Get user's own submitted reviews
    my_reviews = query_db(
        """SELECT r.*, t.name as trainer_name
           FROM reviews r
           LEFT JOIN users t ON r.trainer_id = t.id
           WHERE r.user_id = %s
           ORDER BY r.created_at DESC""",
        (user_id,)
    )

    # For members, fetch active trainers to rate
    trainers_list = []
    if user_role == 'MEMBER':
        trainers_list = query_db(
            """SELECT u.id, u.name, t.specialization, t.experience
               FROM users u
               JOIN trainers t ON u.id = t.user_id
               WHERE u.status = 'active'
               ORDER BY u.name ASC"""
        )

    return render_template(
        'member/feedback.html' if user_role == 'MEMBER' else 'trainer/feedback.html',
        my_reviews=my_reviews,
        trainers_list=trainers_list
    )

@review_bp.route('/submit-webpage', methods=['POST'])
@login_required
def submit_webpage_review():
    """Members and Trainers can submit feedback/review for the Gymkhana webpage/platform."""
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'User')
    user_role = session.get('user_role', 'MEMBER')

    rating = request.form.get('rating', type=int)
    title = request.form.get('title', '').strip()
    comment = request.form.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        flash('Please select a star rating between 1 and 5.', 'danger')
        return redirect(url_for('review.my_feedback'))

    if not comment:
        flash('Please provide your review feedback comment.', 'danger')
        return redirect(url_for('review.my_feedback'))

    # Insert into reviews table as pending
    review_id = execute_db(
        """INSERT INTO reviews (user_id, review_type, rating, title, comment, status)
           VALUES (%s, 'webpage', %s, %s, %s, 'pending')""",
        (user_id, rating, title or f"{user_role.capitalize()} Review", comment)
    )

    log_activity(user_id, user_role, 'REVIEW_SUBMITTED', f"Submitted webpage review with rating {rating}★")

    # Notify administrators about new review pending approval
    admins = query_db("SELECT u.id FROM users u JOIN roles r ON u.role_id = r.id WHERE LOWER(r.name) = 'admin'")
    for admin in admins:
        send_notification(
            admin['id'],
            "New Webpage Review Pending Approval",
            f"{user_name} ({user_role}) submitted a {rating}-star webpage review. Please review and moderate.",
            "info"
        )

    flash('Thank you! Your webpage review has been submitted and is pending administrator approval.', 'success')
    return redirect(url_for('review.my_feedback'))

@review_bp.route('/submit-trainer', methods=['POST'])
@login_required
@role_required('MEMBER')
def submit_trainer_review():
    """Members can rate their trainer and provide feedback."""
    member_id = session.get('user_id')
    member_name = session.get('user_name', 'Member')

    trainer_id = request.form.get('trainer_id', type=int)
    rating = request.form.get('rating', type=int)
    title = request.form.get('title', '').strip()
    comment = request.form.get('comment', '').strip()

    if not trainer_id:
        flash('Please select a trainer to rate.', 'danger')
        return redirect(url_for('review.my_feedback'))

    if not rating or rating < 1 or rating > 5:
        flash('Please select a star rating between 1 and 5.', 'danger')
        return redirect(url_for('review.my_feedback'))

    if not comment:
        flash('Please provide your feedback regarding the trainer.', 'danger')
        return redirect(url_for('review.my_feedback'))

    # Verify trainer exists
    trainer = query_db("SELECT u.name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s AND LOWER(r.name) = 'trainer'", (trainer_id,), one=True)
    if not trainer:
        flash('Selected trainer not found.', 'danger')
        return redirect(url_for('review.my_feedback'))

    execute_db(
        """INSERT INTO reviews (user_id, review_type, trainer_id, rating, title, comment, status)
           VALUES (%s, 'trainer', %s, %s, %s, %s, 'pending')""",
        (member_id, trainer_id, rating, title or f"Feedback for {trainer['name']}", comment)
    )

    log_activity(member_id, 'MEMBER', 'TRAINER_RATED', f"Rated trainer {trainer['name']} ({rating}★)")

    # Notify trainer and admin
    send_notification(
        trainer_id,
        "New Member Rating Submitted",
        f"Member {member_name} submitted a {rating}★ review for you. It will appear on your profile once approved by admin.",
        "info"
    )

    admins = query_db("SELECT u.id FROM users u JOIN roles r ON u.role_id = r.id WHERE LOWER(r.name) = 'admin'")
    for admin in admins:
        send_notification(
            admin['id'],
            "New Trainer Review Pending Approval",
            f"Member {member_name} rated trainer {trainer['name']} ({rating}★). Awaiting your approval.",
            "info"
        )

    flash(f"Your rating and feedback for {trainer['name']} has been submitted for admin approval! Thank you.", 'success')
    return redirect(url_for('review.my_feedback'))

@review_bp.route('/trainer-ratings')
@login_required
@role_required('TRAINER')
def trainer_ratings():
    """Trainers can view all approved ratings and feedback given to them by members."""
    trainer_id = session.get('user_id')

    # Approved reviews for this trainer
    reviews = query_db(
        """SELECT r.*, u.name as member_name, u.email as member_email
           FROM reviews r
           JOIN users u ON r.user_id = u.id
           WHERE r.review_type = 'trainer' AND r.trainer_id = %s AND r.status = 'approved'
           ORDER BY r.created_at DESC""",
        (trainer_id,)
    )

    # Calculate stats
    total_reviews = len(reviews)
    avg_rating = round(sum(r['rating'] for r in reviews) / total_reviews, 1) if total_reviews > 0 else 0.0

    # Star distribution
    star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in reviews:
        star_counts[r['rating']] = star_counts.get(r['rating'], 0) + 1

    return render_template(
        'trainer/reviews.html',
        reviews=reviews,
        total_reviews=total_reviews,
        avg_rating=avg_rating,
        star_counts=star_counts
    )
