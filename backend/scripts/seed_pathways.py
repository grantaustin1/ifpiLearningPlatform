"""Seed the IFPI qualification tracks from the curriculum PDFs (June 2026).

Creates (idempotent, matched by course/path title in org 1):
  - 3 DRAFT courses scaffolded with one TEXT slide per curriculum "bite"
  - Prerequisites: Module 1 (294) -> both Module 2s; Facility M2 -> M3
  - 2 PUBLISHED qualification LearningPaths with NQF/credit metadata

Usage: python scripts/seed_pathways.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from models import (  # noqa: E402
    Course, CoursePrerequisite, CourseSlide, CourseStatus, LearningPath,
    LearningPathItem, LearningPathStatus, SlideType,
)

ORG, ADMIN = 1, 1
MODULE1_ID = 294

M2_FACILITY = [
    ("2.1", "Facility Intro & US 254459", 10, "Facility utilization standards, the NQF Level 5 unit standard, assessors and the Portfolio of Evidence (PoE)."),
    ("2.2", "Physical Facility Inspection", 15, "Inspection protocols for gym floors, studios, wet areas and equipment zones."),
    ("2.3", "Operational Rules & Policies", 12, "Operating hours, access control, safety policies and rule enforcement."),
    ("2.4", "Amenities & Information Desk", 10, "Providing participant information at the amenities and information desk."),
    ("2.5", "Dress Code & Gym Etiquette", 12, "Acceptable attire, weight re-racking, hygiene and cleanliness standards."),
    ("2.6", "Cardiorespiratory Equipment", 15, "Mechanics, advantages and disadvantages of the treadmill, elliptical, cycle, rower and stair climber."),
    ("2.7", "Resistance & Core Equipment", 15, "Free weights, weight stacks, medicine balls, resistance bands and kettlebells."),
    ("2.8", "Instructing Equipment Use", 15, "Correct set-up, posture, tempo, breathing and safety when instructing equipment use."),
    ("2.9", "Supervision & Special Needs", 15, "Monitoring technique, accommodating special needs, handling non-compliance and AED access."),
]

M3_TRAINING = [
    ("3.1", "Exercise Training Introduction", 10, "Definitions of exercise training and the aligned unit standards."),
    ("3.2", "Sedentary Lifestyle Risks", 15, "Obesity, heart disease, diabetes risk and other consequences of inactivity."),
    ("3.3", "Concepts of Health & Wellness", 12, "The WHO definition of health and personal responsibility for wellness."),
    ("3.4", "Components of Fitness", 15, "Health-related versus skill-related fitness components."),
    ("3.5", "General Principles of Training", 15, "Overload, specificity, periodization, progression, reversibility and threshold."),
    ("3.6", "The FITT Principles", 12, "Frequency, Intensity, Time, Type and the ACSM guidelines."),
    ("3.7", "Cardiorespiratory Endurance", 15, "Heart rate zones and fat metabolism during endurance work."),
    ("3.8", "Strength Training Methods", 12, "Power, muscular endurance, circuit training and free weights versus machines."),
    ("3.9", "Flexibility & Stretching", 12, "Static, ballistic and contract-relax stretching techniques."),
    ("3.10", "Sport-Related Training", 12, "Speed, agility, power and plyometric training."),
    ("3.11", "Warm-up & Cool-down Theory", 12, "Objectives, exercise selection and recovery principles."),
    ("3.12", "Practical Warm-up Drills", 15, "Lifting-specific and conditioning-specific warm-up drills."),
    ("3.13", "Practical Cool-down Stretches", 12, "Post-workout flexibility exercises."),
    ("3.14", "Pre-Participation Screening", 12, "Health History Questionnaire (HHQ) and PAR-Q screening."),
    ("3.15", "Readiness to Change Model", 12, "The transtheoretical stages of behaviour change."),
    ("3.16", "Exercise Prescriptions Pad", 10, "ACSM and Exercise-is-Medicine prescription tools."),
    ("3.17", "Body Composition Concepts", 12, "Fat-lean ratio and hydrostatic weighing principles."),
    ("3.18", "Skinfold Thickness Calipers", 15, "Estimation, formulas and caliper calibration."),
    ("3.19", "Skinfold 7 Sites Technique", 15, "Anatomical locations and pinch directions for the 7-site protocol."),
    ("3.20", "BIA & Body Mass Index", 12, "Bio-electrical impedance principles, BMI formula and categories."),
    ("3.21", "Cardiorespiratory Assessments", 15, "Cooper 12-minute run, VO2 Max and the Bruce treadmill protocol."),
    ("3.22", "Strength & Endurance Testing", 15, "Push-up test, core stability and vertical jump assessments."),
    ("3.23", "Agility Field Tests", 12, "Illinois Agility test and shuttle runs."),
    ("3.24", "Testing Order & YMCA Protocol", 12, "Optimal testing order and the YMCA protocol."),
    ("3.25", "Contraindications to Testing", 15, "Absolute and relative contraindications to exercise testing."),
    ("3.26", "Resistance Program Design", 12, "The OPT model and acute variable manipulation."),
    ("3.27", "Reps, Sets & Intensity Continuum", 15, "Power, strength and stabilization rep ranges."),
    ("3.28", "Repetition Tempo", 12, "Time under tension for different training goals."),
    ("3.29", "Rest Intervals & Energy Sources", 15, "How rest intervals affect the three energy systems."),
    ("3.30", "Training Volume & Frequency", 12, "Total work and weekly frequency recommendations."),
    ("3.31", "Exercise Selection Continuum", 15, "Stable to unstable environments, single- versus multi-joint choices."),
    ("3.32", "Periodization Training Plans", 15, "Macrocycles, mesocycles and microcycles."),
    ("3.33", "Developing Beginner Workouts", 15, "High-frequency full-body splits with foundational exercises."),
    ("3.34", "Intermediate & Advanced Splits", 15, "Training splits and sample routines for progressing clients."),
    ("3.35", "Older Adults Exercise Selection", 15, "Strengthening and cardio programming for the elderly."),
    ("3.36", "Overweight & Obese Coaching", 15, "A size-sensitive coaching approach and its challenges."),
    ("3.37", "Overcoming Barriers to Exercise", 15, "Identifying and addressing common barriers to adherence."),
    ("3.38", "Motivation & Adherence Methods", 15, "Self-efficacy, feedback loops and support networks."),
    ("3.39", "Workout Progress Monitoring", 15, "Journaling, tracking tonnage and reading adaptation."),
    ("3.40", "GAS & Avoiding Adaptation", 15, "Alarm, resistance and exhaustion phases; deloading strategies."),
    ("3.41", "Preventing Plateaus: Tonnage", 15, "Changing sets/reps and rotating exercises to keep progressing."),
    ("3.42", "Aerobic Classes & Intensity", 12, "Class levels and choreography complexity."),
    ("3.43", "Types of Aerobic Classes", 15, "High-, low- and mid-tempo, step and circuit formats."),
    ("3.44", "Choreography Phrasing", 15, "Music phrases and structuring combinations."),
    ("3.45", "Aerobics Setting & Ventilation", 10, "Environmental requirements for group classes."),
    ("3.46", "Heart Rate Zone Monitoring", 15, "HR formulas, target zones and MET levels."),
    ("3.47", "Step & Kickboxing Basics", 15, "Footwork, punches and kicks fundamentals."),
    ("3.48", "Injury First Aid: RICE & Ethics", 15, "Shin splints, the RICE protocol and professional ethics."),
]

M2_GROUP = [
    ("2.1", "Evolution of Group Exercise & Aerobics", 10, "Historical overview of group exercise and aerobics."),
    ("2.2", "The Six Dimensions of Wellness", 12, "Physical, social, emotional, intellectual, occupational and spiritual wellness."),
    ("2.3", "Components of Fitness in Group Setting", 15, "Cardio endurance, anaerobic capacity, strength, endurance, power, flexibility, coordination, body composition and recovery."),
    ("2.4", "Aerobic Training Guidelines", 15, "ACSM recommendations for intensity, duration and frequency."),
    ("2.5", "Anaerobic Training Principles", 12, "High-intensity training for lactic and alactic systems; exercise-to-rest ratios."),
    ("2.6", "Strength & Endurance Training Variables", 12, "Prescribing variables for strength and muscular endurance."),
    ("2.7", "Power & Flexibility Training Methods", 12, "Safe plyometrics and static, dynamic and PNF stretching."),
    ("2.8", "Body Composition & Training Overload", 10, "Body composition standards; progressive overload, specificity and reversibility."),
    ("2.9", "The Practical & Psychological Role of Music", 12, "Music for timing, tempo, mood, motivation and engagement."),
    ("2.10", "Structural Elements of Music & Phrasing", 15, "Beats, rhythm, meter and the 32-count block as the core choreography unit."),
    ("2.11", "Tempo, Accents & Musical Variations", 12, "Choosing BPM for safety and intensity; manipulating rhythm."),
    ("2.12", "Advanced Phrasing: Cross-Phrasing & Linking", 12, "Cross-phrasing and linking musical phrases in choreography."),
    ("2.13", "Commercial vs. Pre-Mixed Fitness Music", 10, "Comparing fitness music types and teaching to the beat."),
    ("2.14", "Music Styles, Moods & BPM Ranges", 12, "Matching styles and BPM ranges to demographics and exercise types."),
    ("2.15", "Legal, Copyright & Licensing Frameworks", 12, "Public performance rights, royalties and licensing options."),
    ("2.16", "Environmental Facility Design & Equipment", 12, "Flooring, acoustics, ventilation, temperature and sound systems."),
    ("2.17", "Sound Safety & OSHA Decibel Limits", 10, "Preventing hearing loss: OSHA and IDEA volume standards."),
    ("2.18", "Instructional Cueing Methodology", 12, "Verbal and non-verbal cueing for seamless, anticipatory transitions."),
    ("2.19", "Visual Mirroring & Vocal Motivation", 12, "Mirror-image movement and voice inflection for coordination and motivation."),
    ("2.20", "Class Management: Introductions & Conclusions", 12, "Greeting, class introduction, reassuring newcomers and closing well."),
    ("2.21", "Class Progression & Session Planning", 15, "The standard 60-minute class template and formal session plans."),
    ("2.22", "Choreography Progressions & Teaching Styles", 15, "Linear progression, add-on, small segments, drill-a-skill and pyramid methods."),
    ("2.23", "Step Aerobics Technical Mastery", 15, "Step height limits, floor space, landing technique and common errors."),
    ("2.24", "Basic Step Move Execution & Mechanics", 15, "Biomechanical breakdown and count variations of foundational step patterns."),
    ("2.25", "Kickboxing Aerobics & Injury Protocols", 15, "Stance, punch and kick mechanics, fatigue scanning and RICE."),
]

COURSES = [
    {
        "title": "Module 2: Utilizing the Fitness Facility",
        "category": "Fitness Instructor Track",
        "cover_color": "bg-sky-600",
        "description": "Facility operations & safety, equipment biomechanics and gym-floor supervision. Aligned to US 254459: Supervise the use of a fitness facility (Level 5, 8 Credits). 9 micro-learning bites.",
        "bites": M2_FACILITY,
    },
    {
        "title": "Module 3: Principles of Exercise Training & Instruction",
        "category": "Fitness Instructor Track",
        "cover_color": "bg-emerald-600",
        "description": "Exercise principles, screening & assessments, programme design, periodization, instruction, monitoring and ethics. Aligned to US 258719, US 243294 and US 258720/258725. 48 micro-learning bites.",
        "bites": M3_TRAINING,
    },
    {
        "title": "Module 2: Group Exercise, Choreography & Instruction",
        "category": "Group Instructor Track",
        "cover_color": "bg-rose-600",
        "description": "Wellness foundations, music phrasing (32-count), cueing, class management, step & kickboxing mastery. Aligned to US 10222: Lead and instruct exercise programmes to music (Level 5, 10 Credits). 25 micro-learning bites.",
        "bites": M2_GROUP,
    },
]

TRACKS = [
    {
        "title": "Fitness Instructor Track",
        "description": "The full Fitness Instructor qualification route: Anatomy & Physiology → Utilizing the Fitness Facility → Principles of Exercise Training & Instruction.",
        "cover_color": "bg-sky-600",
        "meta": {
            "qualification": True,
            "designation": "Professional Fitness Instructor",
            "nqf_level": 4, "total_credits": 28,
            "programme_id": "FIT/INSTRUCT/4/0085",
            "unit_standards": [
                "US 243297 — Apply knowledge of anatomy and physiology to exercise training (L4, 5 cr)",
                "US 254459 — Supervise the use of a fitness facility (L5, 8 cr)",
                "US 258719 — Apply the principles of exercise training (L4, 6 cr)",
                "US 243294 — Recommend an exercise programme or activity (L4, 5 cr)",
                "US 258720/258725 — Instruct exercise to individuals and groups (L4, 10 cr)",
            ],
        },
        "courses": [MODULE1_ID, "Module 2: Utilizing the Fitness Facility",
                    "Module 3: Principles of Exercise Training & Instruction"],
    },
    {
        "title": "Group Exercise Instructor Track",
        "description": "The accelerated Group Exercise route: Anatomy & Physiology → Group Exercise, Choreography & Instruction.",
        "cover_color": "bg-rose-600",
        "meta": {
            "qualification": True,
            "designation": "Certified Group Fitness Coach",
            "nqf_level": 4, "total_credits": 15,
            "programme_id": "FIT/GREXERINSTRUC/4/0088",
            "unit_standards": [
                "US 243297 — Apply knowledge of anatomy and physiology to exercise training (L4, 5 cr)",
                "US 10222 — Lead and instruct exercise programmes for individuals and groups to music (L5, 10 cr)",
            ],
        },
        "courses": [MODULE1_ID, "Module 2: Group Exercise, Choreography & Instruction"],
    },
]

PREREQS = [
    ("Module 2: Utilizing the Fitness Facility", MODULE1_ID),
    ("Module 2: Group Exercise, Choreography & Instruction", MODULE1_ID),
    ("Module 3: Principles of Exercise Training & Instruction",
     "Module 2: Utilizing the Fitness Facility"),
]


def main():
    db = SessionLocal()
    ids: dict[str, int] = {}

    for spec in COURSES:
        existing = db.query(Course).filter(
            Course.organization_id == ORG, Course.title == spec["title"]).first()
        if existing:
            ids[spec["title"]] = existing.id
            print(f"exists: {spec['title']} (#{existing.id})")
            continue
        c = Course(organization_id=ORG, title=spec["title"],
                   description=spec["description"], category=spec["category"],
                   cover_color=spec["cover_color"], status=CourseStatus.DRAFT,
                   duration_minutes=sum(b[2] for b in spec["bites"]),
                   created_by_id=ADMIN)
        db.add(c)
        db.flush()
        for i, (bid, title, mins, summary) in enumerate(spec["bites"]):
            db.add(CourseSlide(
                course_id=c.id, title=f"Bite {bid}: {title}",
                slide_type=SlideType.TEXT, order_index=i, is_required=True,
                content=(f"<h2>{title}</h2><p>{summary}</p>"
                         f"<p><em>Bite {bid} · target duration {mins} minutes."
                         f"</em></p><p>[DRAFT — micro-video to be added]</p>")))
        ids[spec["title"]] = c.id
        print(f"created: {spec['title']} (#{c.id}) with {len(spec['bites'])} slides")

    def cid(ref):
        return ref if isinstance(ref, int) else ids[ref]

    for course_ref, prereq_ref in PREREQS:
        exists = db.query(CoursePrerequisite).filter(
            CoursePrerequisite.course_id == cid(course_ref),
            CoursePrerequisite.prerequisite_course_id == cid(prereq_ref)).first()
        if not exists:
            db.add(CoursePrerequisite(course_id=cid(course_ref),
                                      prerequisite_course_id=cid(prereq_ref)))
            print(f"prereq: #{cid(prereq_ref)} -> #{cid(course_ref)}")

    for spec in TRACKS:
        p = db.query(LearningPath).filter(
            LearningPath.organization_id == ORG,
            LearningPath.title == spec["title"]).first()
        if not p:
            p = LearningPath(organization_id=ORG, title=spec["title"],
                             description=spec["description"],
                             cover_color=spec["cover_color"],
                             status=LearningPathStatus.PUBLISHED,
                             created_by_id=ADMIN)
            db.add(p)
            db.flush()
            print(f"track created: {spec['title']} (#{p.id})")
        p.metadata_json = json.dumps(spec["meta"])
        p.status = LearningPathStatus.PUBLISHED
        existing_items = {i.course_id for i in p.items}
        for order, ref in enumerate(spec["courses"]):
            if cid(ref) not in existing_items:
                db.add(LearningPathItem(path_id=p.id, course_id=cid(ref),
                                        order_index=order, is_required=True))

    db.commit()
    print("done.")
    db.close()


if __name__ == "__main__":
    main()
