"""
Clean the raw StuSync CSVs with pandas and load them into PostgreSQL.

Pipeline:  data/raw/*.csv  ->  clean + validate (pandas)  ->  data/clean/*.csv
           ->  create schema (sql/01_schema.sql)  ->  load into PostgreSQL

Every problem found is written to reports/data_quality_log.csv.

Run:  python scripts/clean_and_load.py
Set DATABASE_URL if your login is different, e.g.
      postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/stusync
"""
import os
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN, REPORTS = ROOT / "data" / "raw", ROOT / "data" / "clean", ROOT / "reports"
CLEAN.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/stusync")

VALID_GRADES = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "F"}
DEPT_MAP = {"CSE": "CSE", "EEE": "EEE", "E.E.E": "EEE", "CIVIL": "CIVIL", "TEXTILE": "TEXTILE"}
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$")

log = []  # one row per issue type


def note(table: str, issue: str, rows: int, action: str) -> None:
    if rows:
        log.append({"table": table, "issue": issue, "rows_affected": int(rows), "action": action})
        print(f"  [{table}] {issue}: {rows} -> {action}")


def clean_students(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    df = df.drop_duplicates()
    note("students", "exact duplicate rows", n - len(df), "removed")

    raw_dept = df["dept_name"].astype(str)
    df["dept_name"] = raw_dept.str.strip().str.upper().map(DEPT_MAP)
    note("students", "inconsistent department names (case/spaces/dots)",
         (raw_dept != df["dept_name"]).sum(), "standardised")

    g = df["gender"].astype(str).str.strip().str.upper().str[0]
    note("students", "mixed gender labels (male/M/F)", (df["gender"] != g).sum(), "standardised to M/F")
    df["gender"] = g

    email = df["email"].fillna("").str.strip()
    missing = email.eq("")
    invalid = ~missing & ~email.str.match(EMAIL_RE)
    note("students", "missing e-mail", missing.sum(), "kept as NULL")
    note("students", "invalid e-mail format", invalid.sum(), "set to NULL for follow-up")
    df["email"] = email.where(~(missing | invalid), None)

    phone = df["phone"].astype(str).str.replace(r"^\+880", "0", regex=True)
    note("students", "phone in +880 format", (phone != df["phone"].astype(str)).sum(), "converted to 01XXXXXXXXX")
    df["phone"] = phone

    dup_id = df.duplicated("student_id", keep="first")
    note("students", "same student_id with different details", dup_id.sum(), "kept first row")
    return df[~dup_id]


def clean_grades(df: pd.DataFrame, valid_ids: set) -> pd.DataFrame:
    raw = df["grade"].astype(str)
    df["grade"] = raw.str.strip().str.upper()
    note("grades", "badly typed grade (case/spaces)", (raw != df["grade"]).sum(), "standardised")

    bad = ~df["grade"].isin(VALID_GRADES)
    note("grades", "invalid grade value", bad.sum(), "removed")
    df = df[~bad]

    orphan = ~df["student_id"].isin(valid_ids)
    note("grades", "grade for unknown student", orphan.sum(), "removed")
    df = df[~orphan]

    dup = df.duplicated(["student_id", "course_id"], keep="first")
    note("grades", "two grades for same student and course", dup.sum(), "kept first")
    return df[~dup]


def clean_enrollments(df: pd.DataFrame, valid_ids: set) -> pd.DataFrame:
    orphan = ~df["student_id"].isin(valid_ids)
    note("enrollments", "enrollment for unknown student", orphan.sum(), "removed")
    return df[~orphan]


def clean_attendance(df: pd.DataFrame) -> pd.DataFrame:
    raw = df["status"].astype(str)
    df["status"] = raw.str.strip().str.upper().str[0].map({"P": "Present", "A": "Absent"})
    note("attendance", "mixed status labels (P/present/A)", (raw != df["status"]).sum(),
         "standardised to Present/Absent")
    return df


def main() -> None:
    print("Cleaning raw data...")
    departments = pd.read_csv(RAW / "departments.csv")
    courses = pd.read_csv(RAW / "courses.csv")
    students = clean_students(pd.read_csv(RAW / "students.csv", dtype={"phone": str}))
    ids = set(students["student_id"])
    enrollments = clean_enrollments(pd.read_csv(RAW / "enrollments.csv"), ids)
    grades = clean_grades(pd.read_csv(RAW / "grades.csv"), ids)
    attendance = clean_attendance(pd.read_csv(RAW / "attendance.csv"))

    tables = {"departments": departments, "courses": courses, "students": students,
              "enrollments": enrollments, "grades": grades, "attendance": attendance}
    for name, df in tables.items():
        df.to_csv(CLEAN / f"{name}.csv", index=False)

    pd.DataFrame(log).to_csv(REPORTS / "data_quality_log.csv", index=False)
    print(f"Data-quality log: {len(log)} issue types, "
          f"{sum(r['rows_affected'] for r in log)} rows affected")

    print("Loading into PostgreSQL...")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        conn.exec_driver_sql((ROOT / "sql" / "01_schema.sql").read_text())
        # order matters: parents before children
        for name in ["departments", "courses", "students", "enrollments", "grades", "attendance"]:
            tables[name].to_sql(name, conn, if_exists="append", index=False, chunksize=5000)
        counts = conn.execute(text("""
            SELECT tableoid::regclass AS fragment, COUNT(*) FROM students
            GROUP BY fragment ORDER BY fragment""")).fetchall()
    for frag, c in counts:
        print(f"  {frag}: {c} students")
    for name, df in tables.items():
        print(f"  {name}: {len(df)} rows loaded")
    print("Done.")


if __name__ == "__main__":
    main()
