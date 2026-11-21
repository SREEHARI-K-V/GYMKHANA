from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.database import query_db, execute_db
from utils.auth import login_required, role_required
from utils.helpers import log_activity

workout_bp = Blueprint('workout', __name__, url_prefix='/workout')

@workout_bp.route('/my-workout')
@login_required
@role_required('MEMBER')
def my_workout():
    member_id = session.get('user_id')
    
    # Active plan
    plan = query_db(
        """SELECT wp.*, u.name as trainer_name 
           FROM workout_plans wp 
           JOIN users u ON wp.trainer_id = u.id 
           WHERE wp.member_id = %s AND wp.status = 'active' 
           ORDER BY wp.id DESC LIMIT 1""",
        (member_id,), one=True
    )
    
    exercises_by_day = {}
    completion_pct = 0
    total_count = 0
    completed_count = 0
    
    if plan:
        exercises = query_db(
            """SELECT we.*, e.name as exercise_name, e.muscle_group, e.equipment, e.instructions,
                      COALESCE(wp.completed, 0) as is_completed, wp.actual_weight, wp.actual_reps
               FROM workout_exercises we
               JOIN exercises e ON we.exercise_id = e.id
               LEFT JOIN workout_progress wp ON wp.workout_exercise_id = we.id AND wp.member_id = %s AND wp.completed_at = CURRENT_DATE
               WHERE we.workout_plan_id = %s
               ORDER BY we.day ASC, we.id ASC""",
            (member_id, plan['id'])
        )
        
        for ex in exercises:
            day = ex['day']
            if day not in exercises_by_day:
                exercises_by_day[day] = []
            exercises_by_day[day].append(ex)
            total_count += 1
            if ex['is_completed']:
                completed_count += 1
                
        if total_count > 0:
            completion_pct = round((completed_count / total_count) * 100)

    all_exercises = query_db("SELECT * FROM exercises ORDER BY muscle_group, name")

    return render_template(
        'member/workout.html',
        plan=plan,
        exercises_by_day=exercises_by_day,
        completion_pct=completion_pct,
        total_count=total_count,
        completed_count=completed_count,
        all_exercises=all_exercises
    )

@workout_bp.route('/complete-exercise', methods=['POST'])
@login_required
@role_required('MEMBER')
def complete_exercise():
    member_id = session.get('user_id')
    workout_exercise_id = request.form.get('workout_exercise_id', type=int)
    actual_weight = request.form.get('actual_weight', type=float)
    actual_reps = request.form.get('actual_reps', type=int)
    completed = 1 if request.form.get('completed') else 0

    if not workout_exercise_id:
        flash('Invalid exercise selection.', 'danger')
        return redirect(url_for('workout.my_workout'))

    # Check if record exists for today
    existing = query_db(
        "SELECT id FROM workout_progress WHERE member_id = %s AND workout_exercise_id = %s AND completed_at = CURRENT_DATE",
        (member_id, workout_exercise_id), one=True
    )

    if existing:
        execute_db(
            """UPDATE workout_progress 
               SET completed = %s, actual_weight = %s, actual_reps = %s 
               WHERE id = %s""",
            (completed, actual_weight, actual_reps, existing['id'])
        )
    else:
        execute_db(
            """INSERT INTO workout_progress (member_id, workout_exercise_id, completed, actual_weight, actual_reps, completed_at)
               VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)""",
            (member_id, workout_exercise_id, completed, actual_weight, actual_reps)
        )

    log_activity(member_id, 'MEMBER', 'WORKOUT_UPDATED', f"Updated workout progress for exercise #{workout_exercise_id}")
    flash('Workout exercise progress updated!', 'success')
    return redirect(url_for('workout.my_workout'))

@workout_bp.route('/ai-finder')
@login_required
@role_required('MEMBER')
def ai_finder():
    """AI Workout Finder for Members."""
    all_muscles = ['Chest', 'Back', 'Legs', 'Shoulders', 'Arms', 'Core', 'Cardio']
    all_equip = ['Barbell', 'Dumbbells', 'Cable Machine', 'Bodyweight', 'Machine', 'Treadmill']
    return render_template('member/ai_workout_finder.html', all_muscles=all_muscles, all_equip=all_equip)

@workout_bp.route('/api/ai-find', methods=['POST'])
@login_required
@role_required('MEMBER')
def api_ai_find():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    muscle_group = data.get('muscle_group', 'all')
    equipment = data.get('equipment', 'all')
    fitness_level = data.get('fitness_level', 'intermediate')

    from utils.ai_engine import ai_find_workout
    result = ai_find_workout(query, muscle_group, equipment, fitness_level)
    return jsonify(result)

