"""
Generate realistic (and deliberately messy) raw CSV data for StuSync.

The raw files imitate what a real student-records export looks like:
inconsistent department names, duplicate rows, missing e-mails,
badly typed grades, mixed attendance labels and a few orphan records.
clean_and_load.py finds and fixes these problems.

Run:  python scripts/generate_data.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # same data every run

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

DEPARTMENTS = {
    "CSE": "Dr. Farhana Akter",
    "EEE": "Dr. Mahmudul Hasan",
    "CIVIL": "Dr. Nusrat Jahan",
    "TEXTILE": "Dr. Rezaul Karim",
}
# messy spellings that appear in the raw export
DEPT_VARIANTS = {
    "CSE": ["CSE", "cse", " CSE ", "Cse"],
    "EEE": ["EEE", "eee", "E.E.E"],
    "CIVIL": ["CIVIL", "Civil", "civil "],
    "TEXTILE": ["TEXTILE", "Textile", "textile"],
}
COURSES = {
    "CSE": ["Structured Programming", "Data Structures", "Algorithms",
            "Database Systems", "Distributed Database", "Machine Learning"],
    "EEE": ["Electrical Circuits", "Electronics I", "Signals and Systems",
            "Power Systems", "Control Engineering", "Digital Electronics"],
    "CIVIL": ["Engineering Mechanics", "Surveying", "Structural Analysis",
              "Fluid Mechanics", "Geotechnical Engineering", "Concrete Design"],
    "TEXTILE": ["Yarn Manufacturing", "Fabric Manufacturing", "Wet Processing",
                "Garment Technology", "Textile Testing", "Apparel Merchandising"],
}
FIRST = ["Sadia", "Nusrat", "Tanvir", "Rafi", "Ayesha", "Mehedi", "Sumaiya", "Arif",
         "Farzana", "Imran", "Tasnim", "Rakib", "Jannat", "Sakib", "Lamia", "Nafis",
         "Maliha", "Fahim", "Riya", "Shanto", "Tahmina", "Asif", "Sabrina", "Zubair"]
LAST = ["Rahman", "Hossain", "Islam", "Ahmed", "Akter", "Khan", "Chowdhury",
        "Uddin", "Sultana", "Karim", "Hasan", "Begum", "Sarker", "Mia"]

# BUBT-style grading: (letter, min mark)
GRADE_SCALE = [("A+", 80), ("A", 75), ("A-", 70), ("B+", 65), ("B", 60),
               ("B-", 55), ("C+", 50), ("C", 45), ("D", 40), ("F", 0)]

STUDENTS_PER_DEPT = 100
SESSIONS_PER_COURSE = 12
TERM_START = date(2025, 1, 12)


def letter_for(mark: float) -> str:
    for letter, cut in GRADE_SCALE:
        if mark >= cut:
            return letter
    return "F"


def main() -> None:
    # ---------- departments ----------
    with open(RAW / "departments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dept_name", "head_of_dept"])
        for d, head in DEPARTMENTS.items():
            w.writerow([d, head])

    # ---------- courses ----------
    courses = []  # (course_id, dept, name, credit)
    cid = 101
    for d, names in COURSES.items():
        for name in names:
            courses.append((cid, d, name, random.choice([3.0, 3.0, 3.0, 1.5])))
            cid += 1
    with open(RAW / "courses.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["course_id", "dept_name", "course_name", "credit"])
        w.writerows(courses)

    # ---------- students (with messy rows) ----------
    students = []  # clean truth: (id, dept, ability)
    rows = []
    sid = 22234100001
    for d in DEPARTMENTS:
        for _ in range(STUDENTS_PER_DEPT):
            first, last = random.choice(FIRST), random.choice(LAST)
            ability = random.gauss(0, 1)  # hidden: drives marks and attendance
            dob = date(2002, 1, 1) + timedelta(days=random.randint(0, 1460))
            email = f"{first}.{last}{sid % 1000}@bubt.edu.bd".lower()
            if random.random() < 0.04:
                email = ""  # missing e-mail
            elif random.random() < 0.02:
                email = email.replace("@", "")  # invalid e-mail
            phone = f"01{random.choice('3456789')}{random.randint(10000000, 99999999)}"
            if random.random() < 0.1:
                phone = "+880" + phone[1:]  # mixed phone format
            row = [sid, random.choice(DEPT_VARIANTS[d]), f"{first} {last}",
                   dob.isoformat(), random.choice(["Male", "Female", "male", "F", "M"]),
                   email, phone, "2025-01-05"]
            rows.append(row)
            students.append((sid, d, ability))
            sid += 1
    # exact duplicates (same student exported twice)
    rows += random.sample(rows, 12)
    random.shuffle(rows)
    with open(RAW / "students.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["student_id", "dept_name", "name", "date_of_birth", "gender",
                    "email", "phone", "enrollment_date"])
        w.writerows(rows)

    # ---------- enrollments, grades, attendance ----------
    enr_rows, grade_rows, att_rows = [], [], []
    eid, gid, aid = 1, 1, 1
    by_dept = {d: [c for c in courses if c[1] == d] for d in DEPARTMENTS}
    for s_id, d, ability in students:
        attend_rate = min(0.99, max(0.35, 0.82 + 0.09 * ability + random.gauss(0, 0.06)))
        for c in random.sample(by_dept[d], 5):
            enr_rows.append([eid, s_id, c[0], "2025-01-10"])
            eid += 1
            present = 0
            for k in range(SESSIONS_PER_COURSE):
                status = "Present" if random.random() < attend_rate else "Absent"
                present += status == "Present"
                # messy labels in the export
                label = random.choice({"Present": ["Present", "present", "P"],
                                       "Absent": ["Absent", "absent", "A"]}[status])
                att_rows.append([aid, s_id, c[0],
                                 (TERM_START + timedelta(days=7 * k)).isoformat(), label])
                aid += 1
            mark = 62 + 9 * ability + 25 * (present / SESSIONS_PER_COURSE - 0.8) + random.gauss(0, 6)
            if random.random() < 0.03:
                continue  # grade not yet submitted
            g = letter_for(mark)
            if random.random() < 0.03:
                g = g.lower() + " "  # badly typed grade
            grade_rows.append([gid, s_id, c[0], g])
            gid += 1
    # a few orphan records: student IDs that do not exist
    for k in range(5):
        enr_rows.append([eid, 99999990000 + k, 101, "2025-01-10"])
        eid += 1
    grade_rows.append([gid, 99999990001, 101, "B"])
    gid += 1
    grade_rows.append([gid, 22234100005, 101, "Z"])  # invalid grade

    for name, header, data in [
        ("enrollments.csv", ["enrollment_id", "student_id", "course_id", "enrollment_date"], enr_rows),
        ("grades.csv", ["grade_id", "student_id", "course_id", "grade"], grade_rows),
        ("attendance.csv", ["attendance_id", "student_id", "course_id", "attendance_date", "status"], att_rows),
    ]:
        with open(RAW / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(data)

    print(f"Raw data written to {RAW}")
    print(f"  students: {len(rows)} rows | enrollments: {len(enr_rows)} | "
          f"grades: {len(grade_rows)} | attendance: {len(att_rows)}")


if __name__ == "__main__":
    main()
