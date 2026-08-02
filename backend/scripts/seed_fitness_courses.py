"""Seed three genuine fitness courses (slides + exams) into the main academy.

Idempotent by course title. Run against live DB and the UAT snapshot:

  cd /app/backend && python scripts/seed_fitness_courses.py
  DATABASE_URL=sqlite:////app/backend/snapshots/pre_uat_ifpi_lms.db \
    python scripts/seed_fitness_courses.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal
from models import (
    Course, CourseSlide, CourseStatus, Exam, ExamQuestion, Organization,
    QuestionType, SlideType, User,
)

COURSES = [
    {
        "title": "Foundations of Exercise Science",
        "description": "The essential science behind training: energy systems, muscular adaptation, and programme variables every fitness professional must understand.",
        "category": "Foundation", "duration_minutes": 60, "cover_color": "bg-emerald-600",
        "slides": [
            ("Welcome & What You'll Learn",
             "<h2>Foundations of Exercise Science</h2><p>This course covers the core science every trainer needs: how the body produces energy, how it adapts to training, and how to manipulate programme variables safely and effectively.</p><ul><li>Energy systems</li><li>Muscular adaptation and progressive overload</li><li>Programme variables: intensity, volume, frequency</li><li>Recovery fundamentals</li></ul>"),
            ("The Three Energy Systems",
             "<h2>The Three Energy Systems</h2><p>The body fuels movement through three overlapping systems:</p><ol><li><strong>ATP-PC (phosphagen)</strong> — immediate energy for maximal efforts up to ~10 seconds (sprints, heavy lifts).</li><li><strong>Glycolytic (anaerobic)</strong> — dominant from ~10 seconds to ~2 minutes of hard effort.</li><li><strong>Oxidative (aerobic)</strong> — sustains longer, lower-intensity activity and drives recovery between efforts.</li></ol><p>All three work simultaneously — intensity and duration decide which dominates.</p>"),
            ("Progressive Overload & Adaptation",
             "<h2>Progressive Overload & Adaptation</h2><p>Muscles, tendons and the nervous system adapt when training demand gradually exceeds what the body is accustomed to.</p><ul><li>Increase <strong>load</strong>, <strong>reps</strong>, <strong>sets</strong>, <strong>range of motion</strong> or <strong>density</strong> — one variable at a time.</li><li>Adaptation happens during <strong>recovery</strong>, not during the session itself.</li><li>Too much, too soon is the most common cause of injury in new clients.</li></ul>"),
            ("Programme Variables",
             "<h2>Programme Variables</h2><p>Every programme is a combination of:</p><ul><li><strong>Intensity</strong> — how hard (load / % of 1RM, RPE)</li><li><strong>Volume</strong> — how much (sets × reps)</li><li><strong>Frequency</strong> — how often per week</li><li><strong>Rest</strong> — between sets and between sessions</li><li><strong>Exercise selection & order</strong> — compound before isolation as a default</li></ul><p>Beginners progress on almost anything; consistency beats complexity.</p>"),
            ("Recovery Fundamentals",
             "<h2>Recovery Fundamentals</h2><p>Training is the stimulus — recovery is where results happen.</p><ul><li><strong>Sleep</strong> — 7–9 hours; the single most powerful recovery tool.</li><li><strong>Protein & energy intake</strong> — adequate fuel supports adaptation.</li><li><strong>Deloads</strong> — planned lighter weeks prevent stagnation and overuse.</li><li>Persistent fatigue, disturbed sleep or declining performance are red flags for under-recovery.</li></ul>"),
            ("Summary & Assessment",
             "<h2>Well done!</h2><p>You now understand energy systems, progressive overload, programme variables and recovery. Take the assessment to earn your certificate.</p>"),
        ],
        "exam": {
            "description": "Test your understanding of energy systems, overload and programme design.",
            "questions": [
                ("Which energy system dominates a maximal 8-second sprint?",
                 ["Oxidative (aerobic)", "Glycolytic", "ATP-PC (phosphagen)", "Lactate shuttle"], "2"),
                ("Progressive overload means…",
                 ["Training to failure every session",
                  "Gradually increasing training demand over time",
                  "Doubling training volume each week",
                  "Only lifting maximal loads"], "1"),
                ("Where does physical adaptation primarily occur?",
                 ["During the workout", "During recovery between sessions",
                  "Only during deload weeks", "During warm-ups"], "1"),
                ("Sets × reps describes which programme variable?",
                 ["Intensity", "Frequency", "Volume", "Density"], "2"),
                ("Adequate sleep is one of the most powerful recovery tools.",
                 ["True", "False"], "true"),
            ],
        },
    },
    {
        "title": "Client Onboarding & Consultation Skills",
        "description": "Run professional first consultations: screening, goal setting, expectation management and turning a prospect into a committed long-term client.",
        "category": "Coaching", "duration_minutes": 45, "cover_color": "bg-sky-600",
        "slides": [
            ("Why Onboarding Matters",
             "<h2>Why Onboarding Matters</h2><p>Most clients decide within the first two sessions whether they trust you. A structured onboarding process:</p><ul><li>Uncovers goals, history and constraints before programming</li><li>Sets professional expectations from day one</li><li>Dramatically improves retention and referrals</li></ul>"),
            ("Pre-Exercise Screening",
             "<h2>Pre-Exercise Screening</h2><p>Before any training begins:</p><ul><li>Use a <strong>PAR-Q+</strong> (or your organisation's equivalent) to flag health risks.</li><li>Record injuries, medications, and relevant medical conditions.</li><li><strong>Refer out</strong> when answers exceed your scope of practice — trainers programme exercise; they do not diagnose or treat.</li></ul>"),
            ("The Consultation Conversation",
             "<h2>The Consultation Conversation</h2><p>Structure the first meeting:</p><ol><li><strong>Listen first</strong> — open questions about goals, history and lifestyle (80% them, 20% you).</li><li><strong>Clarify the real goal</strong> — \"lose weight\" often means energy, confidence or health markers.</li><li><strong>Assess</strong> — simple movement screens beat exhaustive test batteries for beginners.</li><li><strong>Agree the plan</strong> — sessions per week, homework, and how progress will be measured.</li></ol>"),
            ("SMART Goals & Expectation Management",
             "<h2>SMART Goals & Expectation Management</h2><p>Convert wishes into commitments:</p><ul><li><strong>S</strong>pecific · <strong>M</strong>easurable · <strong>A</strong>chievable · <strong>R</strong>elevant · <strong>T</strong>ime-bound</li><li>Anchor expectations honestly: sustainable fat loss ≈ 0.5–1% bodyweight per week.</li><li>Schedule a review every 4–6 weeks — progress reviews are your retention engine.</li></ul>"),
            ("Summary & Assessment",
             "<h2>Great work!</h2><p>You can now screen, consult and onboard a new client professionally. Take the assessment to earn your certificate.</p>"),
        ],
        "exam": {
            "description": "Check your consultation, screening and goal-setting knowledge.",
            "questions": [
                ("What is the primary purpose of a PAR-Q+ style screen?",
                 ["To design the first workout", "To flag health risks before exercise begins",
                  "To measure body composition", "To upsell personal training packages"], "1"),
                ("A client's answers reveal a condition outside your scope. You should…",
                 ["Programme around it quietly", "Refer to an appropriate medical professional",
                  "Ignore it if the client insists", "Diagnose it yourself"], "1"),
                ("In a first consultation, roughly how much of the talking should the client do?",
                 ["About 20%", "About 50%", "About 80%", "None — you present your method"], "2"),
                ("Which of these is a SMART goal?",
                 ["Get fitter", "Lose weight soon",
                  "Lose 4 kg in 10 weeks, training 3× per week", "Train harder"], "2"),
                ("Regular progress reviews improve client retention.",
                 ["True", "False"], "true"),
            ],
        },
    },
    {
        "title": "Gym Health & Safety Essentials",
        "description": "The safety knowledge every gym floor professional needs: hazard prevention, equipment checks, emergency response and incident reporting.",
        "category": "Compliance", "duration_minutes": 40, "cover_color": "bg-amber-600",
        "slides": [
            ("Safety Is a Daily Discipline",
             "<h2>Safety Is a Daily Discipline</h2><p>Most gym incidents are preventable. This course covers the four pillars of floor safety:</p><ul><li>Hazard identification and prevention</li><li>Equipment inspection and maintenance</li><li>Emergency response</li><li>Incident reporting</li></ul>"),
            ("Hazard Identification",
             "<h2>Hazard Identification</h2><ul><li><strong>Housekeeping</strong> — re-rack weights, clear walkways, mop spills immediately and sign the wet area.</li><li><strong>Environment</strong> — adequate lighting, ventilation, and safe spacing between stations.</li><li><strong>Behaviour</strong> — coach safe technique and intervene early with unsafe practices.</li><li>Report hazards you cannot fix immediately — never assume someone else will.</li></ul>"),
            ("Equipment Checks",
             "<h2>Equipment Checks</h2><ul><li>Daily visual checks: cables, pins, upholstery, collars and frames.</li><li><strong>Tag out and remove from service</strong> any faulty equipment — a sign alone is not enough.</li><li>Log maintenance so recurring faults become visible.</li></ul>"),
            ("Emergency Response",
             "<h2>Emergency Response</h2><ul><li>Know the location of <strong>first-aid kits, the AED and emergency exits</strong> on your first day.</li><li>In a medical emergency: make the scene safe, call for help per facility protocol, and only act within your first-aid training.</li><li>Keep your first-aid/CPR certification current.</li></ul>"),
            ("Incident Reporting",
             "<h2>Incident Reporting</h2><ul><li>Report <strong>every</strong> incident and near-miss, however small — patterns prevent the big one.</li><li>Record facts, not opinions: what, where, when, who was involved, action taken.</li><li>Reporting protects members, colleagues, you and the business.</li></ul>"),
            ("Summary & Assessment",
             "<h2>Stay sharp!</h2><p>You've covered hazards, equipment, emergencies and reporting. Take the assessment to earn your certificate.</p>"),
        ],
        "exam": {
            "description": "Verify your gym floor safety knowledge.",
            "questions": [
                ("You find a frayed cable on a machine. The correct action is…",
                 ["Leave a note at reception", "Tag it out and remove it from service",
                  "Let members use it carefully", "Fix it yourself during a quiet hour"], "1"),
                ("A spill on the gym floor should be…",
                 ["Left to evaporate", "Covered with a towel",
                  "Mopped immediately and signed", "Reported at end of shift"], "2"),
                ("On your first day in a new facility you should locate…",
                 ["The manager's office only", "First-aid kit, AED and emergency exits",
                  "The staff room", "The sales desk"], "1"),
                ("Near-misses should be reported even when nobody was hurt.",
                 ["True", "False"], "true"),
                ("An incident report should contain…",
                 ["Your opinion of who was at fault", "Facts: what, where, when, who, action taken",
                  "Only serious injuries", "Nothing — verbal reports suffice"], "1"),
            ],
        },
    },
]


def seed_courses(db, org, admin) -> int:
    """Create the demo fitness courses (idempotent by title). Returns count created."""
    created = 0
    for spec in COURSES:
        if db.query(Course).filter(Course.title == spec["title"],
                                   Course.organization_id == org.id).first():
            print(f"• '{spec['title']}' already exists — skipped")
            continue
        course = Course(
            organization_id=org.id, title=spec["title"],
            description=spec["description"], category=spec["category"],
            status=CourseStatus.PUBLISHED, passing_score=70,
            duration_minutes=spec["duration_minutes"], price_cents=0,
            currency="ZAR", created_by_id=admin.id,
            cover_color=spec["cover_color"],
        )
        db.add(course)
        db.flush()
        for i, (title, content) in enumerate(spec["slides"], 1):
            db.add(CourseSlide(course_id=course.id, title=title, content=content,
                               slide_type=SlideType.TEXT, order_index=i))
        exam = Exam(
            organization_id=org.id, title=f"{spec['title']} Assessment",
            description=spec["exam"]["description"], course_id=course.id,
            time_limit_minutes=15, passing_score=70, max_attempts=3,
            is_published=True, created_by_id=admin.id,
        )
        db.add(exam)
        db.flush()
        for i, (text, opts, correct) in enumerate(spec["exam"]["questions"], 1):
            qtype = QuestionType("TRUE_FALSE" if correct in ("true", "false")
                                 else "MULTIPLE_CHOICE")
            db.add(ExamQuestion(exam_id=exam.id, question_text=text,
                                question_type=qtype, options=opts,
                                correct_answer=correct, points=1, order_index=i))
        print(f"• created '{spec['title']}' ({len(spec['slides'])} slides, "
              f"{len(spec['exam']['questions'])}-question exam)")
        created += 1
    return created


def main() -> None:
    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.slug == "ifpi-main").first()
        admin = db.query(User).filter(User.email == "admin@ifpi.org").first()
        if not org or not admin:
            raise SystemExit("ifpi-main org or admin@ifpi.org missing — run the base seed first")
        seed_courses(db, org, admin)
        db.commit()
    print("done")


if __name__ == "__main__":
    main()
