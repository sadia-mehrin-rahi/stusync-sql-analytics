"""
Run the key SQL queries against PostgreSQL and build an Excel report.

Output: reports/StuSync_Report.xlsx
  Summary              - headline numbers built with Excel formulas (COUNTIFS / AVERAGEIFS)
  Dept_Summary         - average CGPA and pass rate per department + chart
  Attendance_vs_Grade  - grade point and fail rate by attendance band + chart
  At_Risk_Students     - students below 75% attendance with a weak grade
  Data_Quality_Log     - every issue found and fixed while cleaning
  Results_Data         - one row per student-course result (source for pivot tables)

Run:  python scripts/export_report.py
"""
import os
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
OUT = REPORTS / "StuSync_Report.xlsx"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/stusync")

RESULTS_SQL = """
WITH course_attendance AS (
    SELECT student_id, course_id,
           ROUND(100.0 * AVG((status = 'Present')::int), 1) AS attendance_pct
    FROM attendance GROUP BY student_id, course_id
)
SELECT s.student_id, s.name, s.dept_name AS department, c.course_name, c.credit,
       g.grade, gp.point AS grade_point, ca.attendance_pct,
       CASE WHEN ca.attendance_pct >= 75 THEN '75% or more' ELSE 'below 75%' END AS attendance_band,
       CASE WHEN g.grade = 'F' THEN 'Fail' ELSE 'Pass' END AS result
FROM grades g
JOIN students s           ON s.student_id = g.student_id
JOIN courses c            ON c.course_id  = g.course_id
JOIN grade_points gp      ON gp.grade     = g.grade
JOIN course_attendance ca ON ca.student_id = g.student_id AND ca.course_id = g.course_id
ORDER BY s.dept_name, s.student_id, c.course_id
"""

DEPT_SQL = """
WITH student_cgpa AS (
    SELECT g.student_id,
           SUM(gp.point * c.credit) / SUM(c.credit) AS cgpa,
           BOOL_AND(g.grade <> 'F') AS passed_all
    FROM grades g
    JOIN courses c ON c.course_id = g.course_id
    JOIN grade_points gp ON gp.grade = g.grade
    GROUP BY g.student_id
)
SELECT s.dept_name AS department, COUNT(*) AS students,
       ROUND(AVG(sc.cgpa), 2) AS avg_cgpa,
       ROUND(100.0 * AVG(sc.passed_all::int), 1) AS pct_passed_all_courses
FROM student_cgpa sc JOIN students s ON s.student_id = sc.student_id
GROUP BY s.dept_name ORDER BY avg_cgpa DESC
"""

ATTEND_SQL = """
WITH course_attendance AS (
    SELECT student_id, course_id, AVG((status = 'Present')::int) AS rate
    FROM attendance GROUP BY student_id, course_id
)
SELECT CASE WHEN ca.rate >= 0.75 THEN '75% or more' ELSE 'below 75%' END AS attendance_band,
       COUNT(*) AS course_results,
       ROUND(AVG(gp.point), 2) AS avg_grade_point,
       ROUND(100.0 * AVG((g.grade = 'F')::int), 1) AS fail_rate_pct
FROM course_attendance ca
JOIN grades g ON g.student_id = ca.student_id AND g.course_id = ca.course_id
JOIN grade_points gp ON gp.grade = g.grade
GROUP BY attendance_band ORDER BY attendance_band
"""

AT_RISK_SQL = """
WITH course_attendance AS (
    SELECT student_id, course_id,
           ROUND(100.0 * AVG((status = 'Present')::int), 1) AS attendance_pct
    FROM attendance GROUP BY student_id, course_id
)
SELECT s.dept_name AS department, s.student_id, s.name, c.course_name,
       ca.attendance_pct, g.grade
FROM course_attendance ca
JOIN grades g ON g.student_id = ca.student_id AND g.course_id = ca.course_id
JOIN grade_points gp ON gp.grade = g.grade
JOIN students s ON s.student_id = ca.student_id
JOIN courses c ON c.course_id = ca.course_id
WHERE ca.attendance_pct < 75 AND gp.point < 2.50
ORDER BY s.dept_name, ca.attendance_pct
"""

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def style_sheet(ws, df: pd.DataFrame, table_name: str) -> None:
    """Header style, column widths and an Excel Table (filter buttons)."""
    for cell in ws[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for i, col in enumerate(df.columns, start=1):
        width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(width, 40)
    ref = f"A1:{get_column_letter(len(df.columns))}{len(df) + 1}"
    tbl = Table(displayName=table_name, ref=ref)
    tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tbl)
    ws.freeze_panes = "A2"


def add_bar_chart(ws, title, y_title, data_col, n_rows, anchor) -> None:
    chart = BarChart()
    chart.title, chart.y_axis.title = title, y_title
    chart.legend = None
    chart.add_data(Reference(ws, min_col=data_col, min_row=1, max_row=n_rows + 1), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n_rows + 1))
    chart.height, chart.width = 7, 14
    ws.add_chart(chart, anchor)


def main() -> None:
    engine = create_engine(DATABASE_URL)
    results = pd.read_sql(text(RESULTS_SQL), engine)
    dept = pd.read_sql(text(DEPT_SQL), engine)
    attend = pd.read_sql(text(ATTEND_SQL), engine)
    at_risk = pd.read_sql(text(AT_RISK_SQL), engine)
    dq_path = REPORTS / "data_quality_log.csv"
    dq = pd.read_csv(dq_path) if dq_path.exists() else pd.DataFrame()

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        pd.DataFrame().to_excel(xw, sheet_name="Summary")
        dept.to_excel(xw, sheet_name="Dept_Summary", index=False)
        attend.to_excel(xw, sheet_name="Attendance_vs_Grade", index=False)
        at_risk.to_excel(xw, sheet_name="At_Risk_Students", index=False)
        dq.to_excel(xw, sheet_name="Data_Quality_Log", index=False)
        results.to_excel(xw, sheet_name="Results_Data", index=False)

    wb = load_workbook(OUT)
    style_sheet(wb["Dept_Summary"], dept, "DeptSummary")
    style_sheet(wb["Attendance_vs_Grade"], attend, "AttendanceVsGrade")
    style_sheet(wb["At_Risk_Students"], at_risk, "AtRisk")
    if not dq.empty:
        style_sheet(wb["Data_Quality_Log"], dq, "DataQuality")
    style_sheet(wb["Results_Data"], results, "Results")

    add_bar_chart(wb["Dept_Summary"], "Average CGPA by department", "CGPA", 3, len(dept), "G2")
    add_bar_chart(wb["Attendance_vs_Grade"], "Fail rate by attendance band", "Fail rate (%)",
                  4, len(attend), "G2")

    # Summary sheet: live Excel formulas over the Results table
    ws = wb["Summary"]
    ws["A1"] = "StuSync - Academic Performance Report (synthetic data)"
    ws["A1"].font = Font(bold=True, size=14)
    rows = [
        ("Course results analysed", "=COUNTA(Results[student_id])"),
        ("Students", f"={results['student_id'].nunique()}"),
        ("Overall average grade point", "=ROUND(AVERAGE(Results[grade_point]),2)"),
        ("Overall fail rate", '=COUNTIFS(Results[result],"Fail")/COUNTA(Results[result])'),
        ("Avg grade point, attendance 75% or more",
         '=ROUND(AVERAGEIFS(Results[grade_point],Results[attendance_band],"75% or more"),2)'),
        ("Avg grade point, attendance below 75%",
         '=ROUND(AVERAGEIFS(Results[grade_point],Results[attendance_band],"below 75%"),2)'),
        ("Fail rate, attendance 75% or more",
         '=COUNTIFS(Results[attendance_band],"75% or more",Results[result],"Fail")'
         '/COUNTIFS(Results[attendance_band],"75% or more")'),
        ("Fail rate, attendance below 75%",
         '=COUNTIFS(Results[attendance_band],"below 75%",Results[result],"Fail")'
         '/COUNTIFS(Results[attendance_band],"below 75%")'),
        ("At-risk course results (see At_Risk_Students)", "=COUNTA(AtRisk[student_id])"),
    ]
    for i, (label, formula) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        c = ws.cell(row=i, column=2, value=formula)
        if "Fail rate" in label or "fail rate" in label:
            c.number_format = "0.0%"
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 14
    ws["A14"] = "Tip: build pivot tables from the Results_Data sheet (Insert > PivotTable > Table: Results)."
    ws["A14"].font = Font(italic=True, color="666666")

    wb.save(OUT)
    print(f"Report written to {OUT}")


if __name__ == "__main__":
    main()
