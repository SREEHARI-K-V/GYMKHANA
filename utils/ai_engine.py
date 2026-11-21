import os
import json
import re
import urllib.request
import urllib.error
from utils.database import query_db

def get_gemini_api_key():
    return os.environ.get('GEMINI_API_KEY', '').strip()

def _call_gemini_api(prompt, system_instruction=None):
    api_key = get_gemini_api_key()
    if not api_key:
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        # Fall back to built-in AI expert engine
        return None

def generate_ai_workout_plan(member_data, goal='muscle_gain', fitness_level='intermediate', days_per_week=4, equipment='Full Gym', limitations='None'):
    """
    AI Workout Plan Generator for Trainers.
    Generates a structured, customized day-by-day workout routine tailored to the member's profile.
    """
    db_exercises = query_db("SELECT id, name, muscle_group, equipment, instructions FROM exercises")
    
    # Map exercises by muscle group for matching
    ex_by_muscle = {}
    for ex in db_exercises:
        mg = ex['muscle_group'].capitalize()
        if mg not in ex_by_muscle:
            ex_by_muscle[mg] = []
        ex_by_muscle[mg].append(ex)

    member_name = member_data.get('name', 'Member')
    weight = member_data.get('weight', 70)
    height = member_data.get('height', 175)
    bmi = member_data.get('bmi', 22.0)
    gender = member_data.get('gender', 'Not specified')

    days_per_week = int(days_per_week)
    if days_per_week < 2:
        days_per_week = 3
    elif days_per_week > 6:
        days_per_week = 6

    # Determine split architecture
    splits = {
        2: [
            {"day": "Day 1 - Upper Body Power", "muscles": ["Chest", "Back", "Shoulders", "Arms"]},
            {"day": "Day 2 - Lower Body & Core", "muscles": ["Legs", "Core", "Cardio"]}
        ],
        3: [
            {"day": "Day 1 - Push Focus (Chest, Delts, Triceps)", "muscles": ["Chest", "Shoulders", "Arms"]},
            {"day": "Day 2 - Pull Focus (Back, Rear Delts, Biceps)", "muscles": ["Back", "Arms"]},
            {"day": "Day 3 - Legs & Core Stability", "muscles": ["Legs", "Core"]}
        ],
        4: [
            {"day": "Day 1 - Upper Body Hypertrophy", "muscles": ["Chest", "Back", "Arms"]},
            {"day": "Day 2 - Lower Body Strength", "muscles": ["Legs", "Core"]},
            {"day": "Day 3 - Push & Shoulder Focus", "muscles": ["Chest", "Shoulders", "Arms"]},
            {"day": "Day 4 - Back & Core Conditioning", "muscles": ["Back", "Core", "Cardio"]}
        ],
        5: [
            {"day": "Day 1 - Chest & Triceps Dominance", "muscles": ["Chest", "Arms"]},
            {"day": "Day 2 - Back & Biceps Thickness", "muscles": ["Back", "Arms"]},
            {"day": "Day 3 - Quads & Calves Power", "muscles": ["Legs"]},
            {"day": "Day 4 - Shoulder Overhead & Traps", "muscles": ["Shoulders", "Core"]},
            {"day": "Day 5 - Posterior Chain & Core HIIT", "muscles": ["Legs", "Core", "Cardio"]}
        ],
        6: [
            {"day": "Day 1 - Push Heavy (Chest / Shoulders)", "muscles": ["Chest", "Shoulders"]},
            {"day": "Day 2 - Pull Heavy (Back / Biceps)", "muscles": ["Back", "Arms"]},
            {"day": "Day 3 - Legs Heavy (Squats / Calves)", "muscles": ["Legs", "Core"]},
            {"day": "Day 4 - Push Volume (Chest / Triceps)", "muscles": ["Chest", "Arms"]},
            {"day": "Day 5 - Pull Volume (Lats / Rows)", "muscles": ["Back", "Arms"]},
            {"day": "Day 6 - Legs Volume & Core Conditioning", "muscles": ["Legs", "Core", "Cardio"]}
        ]
    }

    selected_split = splits.get(days_per_week, splits[4])

    # Goal & level parameter tuning
    if goal == 'fat_loss':
        sets_default = 3
        reps_default = "12-15"
        rest_default = 45
        intensity_notes = "Maintain elevated heart rate, minimize rest between sets, prioritize supersets."
    elif goal == 'strength':
        sets_default = 4
        reps_default = "4-6"
        rest_default = 90
        intensity_notes = "Focus on heavy compound progressive overload. Rest sufficiently for full ATP recovery."
    elif goal == 'endurance':
        sets_default = 3
        reps_default = "15-20"
        rest_default = 30
        intensity_notes = "High-rep circuit pacing. Focus on muscular endurance and oxygen efficiency."
    else:  # muscle_gain (Hypertrophy)
        sets_default = 4
        reps_default = "8-12"
        rest_default = 60
        intensity_notes = "Focus on mind-muscle connection, 2-3 sec eccentric control, and mechanical tension."

    plan_name = f"AI {goal.replace('_', ' ').title()} Blueprint ({days_per_week}-Day)"
    
    rationale = (
        f"AI Program generated for {member_name} ({gender}, BMI: {bmi}). "
        f"Optimized for {goal.replace('_', ' ').title()} at {fitness_level.capitalize()} level. "
        f"{intensity_notes} Designed around a {days_per_week}-day split with progressive volume."
    )

    days_plan = []
    for day_obj in selected_split:
        day_title = day_obj["day"]
        day_exercises = []
        target_muscles = day_obj["muscles"]

        for muscle in target_muscles:
            available = ex_by_muscle.get(muscle, [])
            # Filter by equipment if specified
            if equipment and equipment != 'Full Gym':
                filtered = [e for e in available if equipment.lower() in e.get('equipment', '').lower() or 'bodyweight' in e.get('equipment', '').lower()]
                if filtered:
                    available = filtered

            # Pick 1 or 2 exercises for this muscle
            count = 2 if len(target_muscles) <= 2 else 1
            for ex in available[:count]:
                if any(x['exercise_id'] == ex['id'] for x in day_exercises):
                    continue

                # Estimate target starting weight
                target_weight = "Bodyweight"
                if "barbell" in ex.get('equipment', '').lower():
                    if "chest" in muscle.lower():
                        target_weight = f"{max(30, int(float(weight or 70) * 0.6))} kg"
                    elif "leg" in muscle.lower():
                        target_weight = f"{max(40, int(float(weight or 70) * 0.8))} kg"
                    elif "back" in muscle.lower():
                        target_weight = f"{max(50, int(float(weight or 70) * 0.9))} kg"
                    else:
                        target_weight = "25 kg"
                elif "dumbbell" in ex.get('equipment', '').lower():
                    target_weight = "12-16 kg each"
                elif "cable" in ex.get('equipment', '').lower():
                    target_weight = "25-35 kg"

                day_exercises.append({
                    "exercise_id": ex['id'],
                    "exercise_name": ex['name'],
                    "muscle_group": ex['muscle_group'],
                    "equipment": ex['equipment'],
                    "sets": sets_default,
                    "reps": reps_default,
                    "weight": target_weight,
                    "rest_seconds": rest_default,
                    "instructions": ex.get('instructions', '')
                })

        days_plan.append({
            "day": day_title,
            "exercises": day_exercises
        })

    return {
        "success": True,
        "plan_name": plan_name,
        "rationale": rationale,
        "days_per_week": days_per_week,
        "goal": goal,
        "fitness_level": fitness_level,
        "split": days_plan
    }

def ai_find_workout(query="", muscle_group=None, equipment=None, fitness_level=None):
    """
    AI Workout Finder for Members.
    Analyzes queries or filter tags to return personalized exercise routines and coaching instructions.
    """
    db_exercises = query_db("SELECT id, name, muscle_group, equipment, instructions, description FROM exercises")
    
    query_lower = query.lower().strip() if query else ""
    matched_exercises = []

    # Keywords mapping
    muscle_synonyms = {
        'chest': ['chest', 'bench', 'pecs', 'push-up', 'pushup'],
        'back': ['back', 'lat', 'row', 'deadlift', 'pull-up', 'pullup', 'lats'],
        'legs': ['legs', 'quads', 'hamstrings', 'glutes', 'squat', 'lunge', 'calves', 'calf'],
        'shoulders': ['shoulders', 'delts', 'overhead', 'military', 'lateral', 'face pull'],
        'arms': ['arms', 'biceps', 'triceps', 'curl', 'pushdown', 'dips'],
        'core': ['core', 'abs', 'abdominal', 'plank', 'crunch', 'twist', 'six pack', 'belly'],
        'cardio': ['cardio', 'hiit', 'treadmill', 'run', 'sprint', 'fat burn', 'stamina', 'weight loss']
    }

    # Detect muscle groups from query
    detected_muscles = set()
    if muscle_group and muscle_group != 'all':
        detected_muscles.add(muscle_group.capitalize())
    else:
        for mg, keywords in muscle_synonyms.items():
            if any(kw in query_lower for kw in keywords):
                detected_muscles.add(mg.capitalize())

    # If no specific muscle detected, consider full body
    is_full_body = not detected_muscles or 'full body' in query_lower or 'total body' in query_lower

    # Filter exercises
    for ex in db_exercises:
        ex_muscle = ex['muscle_group'].capitalize()
        ex_equip = ex.get('equipment', '').lower()
        ex_name = ex.get('name', '').lower()
        ex_desc = (ex.get('description', '') + ' ' + ex.get('instructions', '')).lower()

        score = 0
        if is_full_body or ex_muscle in detected_muscles:
            score += 3
        
        # Check query keywords
        if query_lower:
            words = [w for w in re.split(r'\W+', query_lower) if len(w) > 2]
            for word in words:
                if word in ex_name:
                    score += 5
                elif word in ex_equip:
                    score += 3
                elif word in ex_desc:
                    score += 2

        # Equipment match
        if equipment and equipment != 'all':
            if equipment.lower() in ex_equip or (equipment.lower() == 'bodyweight' and 'bodyweight' in ex_equip):
                score += 4
            else:
                score -= 5

        if score > 0:
            matched_exercises.append((score, ex))

    # Sort by relevance
    matched_exercises.sort(key=lambda x: x[0], reverse=True)
    selected = [item[1] for item in matched_exercises[:8]]

    if not selected:
        selected = db_exercises[:6]

    # Generate AI Coach Insights based on the search
    coach_advice = []
    if 'fat' in query_lower or 'loss' in query_lower or 'burn' in query_lower:
        coach_advice.append("🔥 High-Calorie Burn Focus: Keep your rest periods under 45 seconds to maintain cardiovascular momentum.")
    elif 'mass' in query_lower or 'muscle' in query_lower or 'build' in query_lower:
        coach_advice.append("💪 Hypertrophy Focus: Aim for 8-12 repetitions with a controlled 2-second lowering phase on every rep.")
    elif 'home' in query_lower or 'bodyweight' in query_lower:
        coach_advice.append("🏡 Calisthenic Mastery: Focus on peak contraction and pausing at the bottom of movements for maximum muscle fiber recruitment.")
    else:
        coach_advice.append("⚡ Performance Tip: Always complete a 5-minute dynamic warm-up before beginning heavy compound sets.")

    coach_advice.append("💧 Hydration & Recovery: Drink at least 500ml water during your session and log your lifted weights to track progressive overload.")

    # Format result routine
    routine = []
    for ex in selected:
        routine.append({
            "id": ex['id'],
            "name": ex['name'],
            "muscle_group": ex['muscle_group'],
            "equipment": ex['equipment'],
            "target_sets": 3,
            "target_reps": "10-12",
            "rest_seconds": 60,
            "instructions": ex.get('instructions', ''),
            "description": ex.get('description', '')
        })

    return {
        "query": query,
        "detected_muscles": list(detected_muscles) if detected_muscles else ["Full Body"],
        "count": len(routine),
        "coach_advice": coach_advice,
        "exercises": routine
    }
