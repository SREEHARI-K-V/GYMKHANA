# GYMKHANA — Gym Management, Workout & Diet Tracking System

GYMKHANA is a full-featured, professional web application designed as an MCA Major Project. It provides a complete, production-grade platform for gym administrators, certified personal trainers, and gym members.

---

## 🌟 Key Features

### 👤 Member Portal
- **Dashboard**: Personal welcome banner, active membership status card with remaining days countdown and 1-click renewal, current BMI category, today's workout completion rate, and quick shortcuts.
- **Gym Membership & Anytime Renewal**: View active subscription plan, benefits, remaining days progress bar, and renew anytime. Existing days are automatically preserved and added to your new plan cycle.
- **Online Payment Gateway**: Secure checkout with simulated UPI (QR & VPA), Credit/Debit Card, Net Banking, and Gymkhana Quick Pay. Generates instant official tax invoices with printable receipts.
- **Payment History Ledger**: Complete audit history of past subscriptions and online payments with downloadable/printable invoice receipts.
- **AI Workout Finder & Fitness Coach**: Search routines using natural language (e.g. "30-min dumbbell workout for chest and biceps"), explore preset chips, filter by muscle groups and equipment, and receive AI coaching insights.
- **Personalized Workout & Diet Management**: Daily checklists, actual weight/reps tracking, macro nutrient targets (Protein, Carbs, Fat) by meal type.
- **Reviews & Feedback**: Submit reviews for Gymkhana webpage/facilities and rate personal trainers with 1-5 stars and feedback comments. View submission moderation status.
- **Fitness & BMI Progress Analytics**: Chart.js progression charts tracking weight and body measurements over time.
- **Gym Branch Finder**: Interactive Leaflet.js map with browser geolocation and distance calculation.
- **In-App Notifications**: Real-time bell notification drawer for payment confirmations, plan renewals, and trainer updates.

### 🏋️ Trainer Portal
- **Dashboard**: Overview of assigned athletes, coaching rating badge (⭐ aggregate score from members), active membership counts, and member progress.
- **AI Workout Plan Generator**: 1-click AI generation of personalized, multi-day workout splits based on member BMI, weight, fitness level, training frequency, equipment, and injuries. Auto-populates and assigns directly to member.
- **Member Detail & Plan Builder**: Complete view of member stats and manual or AI-assisted workout and diet plan assignments.
- **My Ratings & Member Reviews**: View approved ratings and feedback testimonials given by members with star breakdown analytics.
- **Platform Feedback**: Submit webpage feedback and facilities reviews for admin approval.

### 🛡️ Admin Portal
- **Dashboard**: High-level KPI metrics including Total Members, Total Trainers, Active Subscriptions, Total Revenue, Online Gateway Collections, and Pending Community Reviews.
- **Review Moderation Center**: Approve, reject, or delete community reviews (webpage and trainer feedback) with real-time status filtering (Pending, Approved, Rejected).
- **Online Payments Management**: Searchable ledger of all online transactions with payment method breakdown (UPI, Card, NetBanking), revenue analytics, and printable invoices.
- **User & Trainer Management**: Full CRUD operations for members and trainers.
- **Membership Plan Management**: Configure plan pricing, durations, benefits, and activation status.
- **Gym Branch Management**: Map coordinates, hours, and branch facilities.
- **Reporting Module & Activity Logs**: Export progress reports to CSV and view detailed system audit logs.

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, CSS3 (Vanilla Custom Gym SaaS Design System), JavaScript (ES6), Bootstrap 5, Bootstrap Icons, **Chart.js**, **Leaflet.js / OpenStreetMap**.
- **Backend**: Python 3.11, **Flask** (Flask Blueprints modular architecture), Werkzeug Security.
- **Database**: **MySQL** (`mysql.connector` / `schema.sql`) with universal parameterization. Seamless built-in fallback for zero-setup execution.
- **Architecture**: Modular Flask Blueprints (`auth`, `member`, `trainer`, `admin`, `subscription`, `workout`, `diet`, `progress`, `gym`, `notification`, `reports`).

---

## 🚀 Quick Setup & Installation Guide

### 1. Prerequisites
- Python 3.8+
- MySQL Server (optional; application will connect to MySQL or run with embedded fallback automatically)

### 2. Clone / Workspace Location
Navigate to the project root directory:
```bash
cd C:\Users\RAHUL\.gemini\antigravity\scratch\gymkhana
```

### 3. Install Dependencies
```bash
pip install Flask mysql-connector-python python-dotenv Werkzeug python-dateutil
```

### 4. Database Setup & Seeding
Initialize database schema and populate complete demo data (Users, Trainers, Members, Plans, Branches, Exercises, Sample Workouts, Sample Diets):
```bash
python seed.py
```

### 5. Launch the Application
Run the Flask server:
```bash
python app.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 🔑 Demo Credentials

| Role | Email Address | Password | Description |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@gymkhana.com` | `Admin@123` | Full system control, branch CRUD, user management & CSV reports |
| **Trainer 1** | `trainer1@gymkhana.com` | `Trainer@123` | Strength & Conditioning Specialist |
| **Trainer 2** | `trainer2@gymkhana.com` | `Trainer@123` | Weight Loss & Nutrition Specialist |
| **Member 1** | `member1@gymkhana.com` | `Member@123` | Rahul Sharma (Active Subscription, Assigned Workout & Diet) |
| **Member 2** | `member2@gymkhana.com` | `Member@123` | Anita Roy (Active Subscription, Weight Loss Progress) |

---

## 📂 Project Structure

```
gymkhana/
│
├── app.py                     # Main Flask application entry point
├── config.py                  # Application configuration & DB parameters
├── schema.sql                 # MySQL Database Schema (16 tables)
├── seed.py                    # Seed script for initial demo data
├── README.md                  # Project documentation
│
├── routes/                    # Modular Flask Blueprints
│   ├── auth.py                # Registration, Login, Logout, Profile
│   ├── member.py              # Member Dashboard & metrics
│   ├── subscription.py        # Membership plans & active subscriptions
│   ├── workout.py             # Exercise database & workout tracking
│   ├── diet.py                # Diet plans & nutrition breakdown
│   ├── progress.py            # Weight, BMI & body measurement tracking
│   ├── gym.py                 # Branch finder & Leaflet.js map API
│   ├── notification.py        # In-app notifications & unread counter
│   ├── trainer.py             # Trainer portal, member assignment & plan builder
│   ├── admin.py               # Admin portal, user/trainer/plan/branch CRUD
│   └── reports.py             # System reports & CSV exports
│
├── static/
│   ├── css/
│   │   └── style.css          # Custom Gym SaaS styling
│   └── js/
│       └── main.js            # Sidebar toggle, notification checks & actions
│
├── templates/
│   ├── base.html              # Master layout template with role sidebar
│   ├── index.html             # Public Landing Page
│   ├── auth/                  # Login, Register, Profile templates
│   ├── member/                # Member views (Dashboard, Workout, Diet, Progress, Map, Subscriptions)
│   ├── trainer/               # Trainer views (Dashboard, My Members, Member Detail, Plan Builders)
│   ├── admin/                 # Admin views (Dashboard, Users, Trainers, Plans, Branches, Reports, Logs)
│   └── errors/                # Custom 403, 404, 500 error pages
│
└── utils/
    ├── auth.py                # Password hashing & @login_required / @role_required
    ├── database.py            # Parameterized SQL database execution helper
    └── helpers.py             # BMI calculator, activity logger & notification helper
```

---

## 👨‍🎓 Major Project Verification & Features Matrix

- [x] **Authentication**: Password hashing (`werkzeug.security`), session handling, duplicate email prevention.
- [x] **Authorization**: Role-based access control (`@role_required('MEMBER', 'TRAINER', 'ADMIN')`).
- [x] **Subscriptions**: Dynamic remaining days calculation, status badges, payment history.
- [x] **Workouts**: Day-wise workout split, target sets/reps/weight, actual logging, completion %.
- [x] **Diet**: Daily calorie & macro target tracking, meal breakdown with nutrition math.
- [x] **Fitness Progress**: BMI calculation ($BMI = Weight / Height^2$), category badge, Chart.js progress graphs.
- [x] **Gym Geolocation**: Leaflet OpenStreetMap canvas, browser location query, Haversine distance, turn-by-turn directions.
- [x] **Notifications**: In-app bell dropdown with live unread badge count.
- [x] **Admin Operations**: User CRUD, Trainer CRUD, Plan CRUD, Branch CRUD, Activity Logs, CSV Exports.
#   G Y M K H A N A  
 #   G Y M K H A N A  
 