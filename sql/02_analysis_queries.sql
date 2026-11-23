-- =====================================================================
-- StuSync: analysis queries
-- Run in pgAdmin (Query Tool) or:  psql -d stusync -f sql/02_analysis_queries.sql
-- =====================================================================

-- Q1. Fragment sizes: how many students sit in each department fragment
SELECT tableoid::regclass AS fragment,
       COUNT(*)           AS students
FROM students
GROUP BY fragment
ORDER BY fragment;

-- Q2. Reading the fragments directly and combining them with UNION ALL
--     (what the global "students" table does for you automatically)
SELECT 'CSE' AS dept, COUNT(*) FROM students_cse
UNION ALL SELECT 'EEE',     COUNT(*) FROM students_eee
UNION ALL SELECT 'CIVIL',   COUNT(*) FROM students_civil
UNION ALL SELECT 'TEXTILE', COUNT(*) FROM students_textile;

-- Q3. JOIN: full transcript for one student
SELECT s.student_id, s.name, c.course_name, c.credit, g.grade, gp.point
FROM students s
JOIN grades       g  ON g.student_id = s.student_id
JOIN courses      c  ON c.course_id  = g.course_id
JOIN grade_points gp ON gp.grade     = g.grade
WHERE s.student_id = 22234100001
ORDER BY c.course_id;

-- Q4. GROUP BY: credit-weighted CGPA per student (top 10)
SELECT s.student_id, s.name, s.dept_name,
       ROUND(SUM(gp.point * c.credit) / SUM(c.credit), 2) AS cgpa
FROM students s
JOIN grades       g  ON g.student_id = s.student_id
JOIN courses      c  ON c.course_id  = g.course_id
JOIN grade_points gp ON gp.grade     = g.grade
GROUP BY s.student_id, s.name, s.dept_name
ORDER BY cgpa DESC
LIMIT 10;

-- Q5. GROUP BY: average CGPA and pass rate per department
WITH student_cgpa AS (
    SELECT g.student_id,
           SUM(gp.point * c.credit) / SUM(c.credit) AS cgpa,
           BOOL_AND(g.grade <> 'F')                  AS passed_all
    FROM grades g
    JOIN courses      c  ON c.course_id = g.course_id
    JOIN grade_points gp ON gp.grade    = g.grade
    GROUP BY g.student_id
)
SELECT s.dept_name,
       COUNT(*)                                            AS students,
       ROUND(AVG(sc.cgpa), 2)                              AS avg_cgpa,
       ROUND(100.0 * AVG(sc.passed_all::int), 1)           AS pct_passed_all_courses
FROM student_cgpa sc
JOIN students s ON s.student_id = sc.student_id
GROUP BY s.dept_name
ORDER BY avg_cgpa DESC;

-- Q6. GROUP BY + HAVING: courses where more than 10% of students failed
SELECT c.course_id, c.course_name, c.dept_name,
       COUNT(*)                                                AS graded,
       SUM(CASE WHEN g.grade = 'F' THEN 1 ELSE 0 END)          AS failed,
       ROUND(100.0 * AVG((g.grade = 'F')::int), 1)             AS fail_rate_pct
FROM grades g
JOIN courses c ON c.course_id = g.course_id
GROUP BY c.course_id, c.course_name, c.dept_name
HAVING AVG((g.grade = 'F')::int) > 0.10
ORDER BY fail_rate_pct DESC;

-- Q7. Subquery: students whose CGPA is above their own department's average
WITH student_cgpa AS (
    SELECT s.student_id, s.name, s.dept_name,
           SUM(gp.point * c.credit) / SUM(c.credit) AS cgpa
    FROM students s
    JOIN grades       g  ON g.student_id = s.student_id
    JOIN courses      c  ON c.course_id  = g.course_id
    JOIN grade_points gp ON gp.grade     = g.grade
    GROUP BY s.student_id, s.name, s.dept_name
)
SELECT student_id, name, dept_name, ROUND(cgpa, 2) AS cgpa
FROM student_cgpa sc
WHERE cgpa > (SELECT AVG(cgpa) FROM student_cgpa x WHERE x.dept_name = sc.dept_name)
ORDER BY dept_name, cgpa DESC;

-- Q8. Window function: top 3 students in each department
WITH student_cgpa AS (
    SELECT s.student_id, s.name, s.dept_name,
           SUM(gp.point * c.credit) / SUM(c.credit) AS cgpa
    FROM students s
    JOIN grades       g  ON g.student_id = s.student_id
    JOIN courses      c  ON c.course_id  = g.course_id
    JOIN grade_points gp ON gp.grade     = g.grade
    GROUP BY s.student_id, s.name, s.dept_name
)
SELECT dept_name, rnk, name, ROUND(cgpa, 2) AS cgpa
FROM (SELECT *, RANK() OVER (PARTITION BY dept_name ORDER BY cgpa DESC) AS rnk
      FROM student_cgpa) ranked
WHERE rnk <= 3
ORDER BY dept_name, rnk;

-- Q9. Attendance vs result: does attending class change the grade?
WITH course_attendance AS (
    SELECT student_id, course_id,
           AVG((status = 'Present')::int) AS attendance_rate
    FROM attendance
    GROUP BY student_id, course_id
)
SELECT CASE WHEN ca.attendance_rate >= 0.75 THEN '75% or more'
            ELSE 'below 75%' END                       AS attendance_band,
       COUNT(*)                                        AS course_results,
       ROUND(AVG(gp.point), 2)                         AS avg_grade_point,
       ROUND(100.0 * AVG((g.grade = 'F')::int), 1)     AS fail_rate_pct
FROM course_attendance ca
JOIN grades       g  ON g.student_id = ca.student_id AND g.course_id = ca.course_id
JOIN grade_points gp ON gp.grade = g.grade
GROUP BY attendance_band
ORDER BY attendance_band;

-- Q10. At-risk list: below 75% attendance AND grade point under 2.50 in the same course
WITH course_attendance AS (
    SELECT student_id, course_id,
           ROUND(100.0 * AVG((status = 'Present')::int), 1) AS attendance_pct
    FROM attendance
    GROUP BY student_id, course_id
)
SELECT s.dept_name, s.student_id, s.name, c.course_name,
       ca.attendance_pct, g.grade
FROM course_attendance ca
JOIN grades       g  ON g.student_id = ca.student_id AND g.course_id = ca.course_id
JOIN grade_points gp ON gp.grade = g.grade
JOIN students     s  ON s.student_id = ca.student_id
JOIN courses      c  ON c.course_id  = ca.course_id
WHERE ca.attendance_pct < 75 AND gp.point < 2.50
ORDER BY s.dept_name, ca.attendance_pct;
