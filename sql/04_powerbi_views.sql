-- =====================================================================
-- StuSync: reporting views for Power BI
-- Power BI imports these two views instead of the raw tables.
-- Run once in pgAdmin (Query Tool) after clean_and_load.py.
-- =====================================================================

-- One row per student-course result, with attendance and risk flag
CREATE OR REPLACE VIEW vw_course_results AS
WITH course_attendance AS (
    SELECT student_id, course_id,
           ROUND(100.0 * AVG((status = 'Present')::int), 1) AS attendance_pct
    FROM attendance
    GROUP BY student_id, course_id
)
SELECT s.student_id,
       s.name,
       s.dept_name                                                     AS department,
       c.course_id,
       c.course_name,
       c.credit,
       g.grade,
       gp.point                                                        AS grade_point,
       ca.attendance_pct,
       CASE WHEN ca.attendance_pct >= 75 THEN '75% or more' ELSE 'Below 75%' END AS attendance_band,
       CASE WHEN g.grade = 'F' THEN 'Fail' ELSE 'Pass' END             AS result,
       (ca.attendance_pct < 75 AND gp.point < 2.50)                    AS is_at_risk
FROM grades g
JOIN students s           ON s.student_id = g.student_id
JOIN courses c            ON c.course_id  = g.course_id
JOIN grade_points gp      ON gp.grade     = g.grade
JOIN course_attendance ca ON ca.student_id = g.student_id AND ca.course_id = g.course_id;

-- One row per student: credit-weighted CGPA and average attendance
CREATE OR REPLACE VIEW vw_student_summary AS
SELECT student_id,
       name,
       department,
       ROUND(SUM(grade_point * credit) / SUM(credit), 2) AS cgpa,
       ROUND(AVG(attendance_pct), 1)                     AS avg_attendance_pct,
       COUNT(*)                                          AS courses_graded,
       SUM(CASE WHEN result = 'Fail' THEN 1 ELSE 0 END)  AS courses_failed
FROM vw_course_results
GROUP BY student_id, name, department;
