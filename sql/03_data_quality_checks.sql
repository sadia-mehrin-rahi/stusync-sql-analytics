-- =====================================================================
-- StuSync: data-quality checks (run after loading)
-- Every check should return 0 problem rows on clean data.
-- =====================================================================

-- DQ1. Orphan enrollments: student_id not found in any fragment
SELECT 'orphan enrollments' AS check_name, COUNT(*) AS problems
FROM enrollments e
WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.student_id = e.student_id)

UNION ALL
-- DQ2. Orphan grades
SELECT 'orphan grades', COUNT(*)
FROM grades g
WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.student_id = g.student_id)

UNION ALL
-- DQ3. Grade without a matching enrollment
SELECT 'grade without enrollment', COUNT(*)
FROM grades g
LEFT JOIN enrollments e ON e.student_id = g.student_id AND e.course_id = g.course_id
WHERE e.enrollment_id IS NULL

UNION ALL
-- DQ4. Student enrolled in a course from another department
SELECT 'cross-department enrollment', COUNT(*)
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN courses  c ON c.course_id  = e.course_id
WHERE s.dept_name <> c.dept_name

UNION ALL
-- DQ5. Same student_id stored in two fragments
SELECT 'student_id in more than one fragment', COUNT(*)
FROM (SELECT student_id FROM students GROUP BY student_id HAVING COUNT(*) > 1) d

UNION ALL
-- DQ6. Attendance outside the enrolled courses
SELECT 'attendance without enrollment', COUNT(*)
FROM attendance a
LEFT JOIN enrollments e ON e.student_id = a.student_id AND e.course_id = a.course_id
WHERE e.enrollment_id IS NULL;

-- Follow-up list (not an error): students with no usable e-mail
SELECT dept_name, student_id, name
FROM students
WHERE email IS NULL
ORDER BY dept_name, student_id;

-- Follow-up list: enrolled courses still missing a grade
SELECT e.student_id, e.course_id
FROM enrollments e
LEFT JOIN grades g ON g.student_id = e.student_id AND g.course_id = e.course_id
WHERE g.grade_id IS NULL
ORDER BY e.student_id;
