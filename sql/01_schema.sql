-- =====================================================================
-- StuSync: schema (PostgreSQL 13+)
-- Student data is horizontally fragmented by department using
-- PostgreSQL LIST partitioning: one fragment per department.
-- =====================================================================

DROP TABLE IF EXISTS attendance, grades, enrollments, courses, students, departments CASCADE;

CREATE TABLE departments (
    dept_name     VARCHAR(20) PRIMARY KEY,
    head_of_dept  VARCHAR(100) NOT NULL
);

-- Parent (global) table: queries on "students" automatically read all fragments
CREATE TABLE students (
    student_id       BIGINT       NOT NULL,
    dept_name        VARCHAR(20)  NOT NULL REFERENCES departments(dept_name),
    name             VARCHAR(100) NOT NULL,
    date_of_birth    DATE,
    gender           CHAR(1)      CHECK (gender IN ('M', 'F')),
    email            VARCHAR(120),
    phone            VARCHAR(20),
    enrollment_date  DATE,
    -- PostgreSQL requires the partition key inside the primary key
    PRIMARY KEY (student_id, dept_name)
) PARTITION BY LIST (dept_name);

-- Horizontal fragments (one per department)
CREATE TABLE students_cse     PARTITION OF students FOR VALUES IN ('CSE');
CREATE TABLE students_eee     PARTITION OF students FOR VALUES IN ('EEE');
CREATE TABLE students_civil   PARTITION OF students FOR VALUES IN ('CIVIL');
CREATE TABLE students_textile PARTITION OF students FOR VALUES IN ('TEXTILE');

CREATE TABLE courses (
    course_id    INT          PRIMARY KEY,
    dept_name    VARCHAR(20)  NOT NULL REFERENCES departments(dept_name),
    course_name  VARCHAR(100) NOT NULL,
    credit       NUMERIC(3,1) NOT NULL CHECK (credit > 0)
);

-- Because students is partitioned, its primary key is (student_id, dept_name),
-- so the tables below cannot hold a simple foreign key to student_id.
-- Referential integrity is checked instead by sql/03_data_quality_checks.sql.
CREATE TABLE enrollments (
    enrollment_id    INT     PRIMARY KEY,
    student_id       BIGINT  NOT NULL,
    course_id        INT     NOT NULL REFERENCES courses(course_id),
    enrollment_date  DATE,
    UNIQUE (student_id, course_id)
);

CREATE TABLE grades (
    grade_id    INT        PRIMARY KEY,
    student_id  BIGINT     NOT NULL,
    course_id   INT        NOT NULL REFERENCES courses(course_id),
    grade       VARCHAR(2) NOT NULL
                CHECK (grade IN ('A+','A','A-','B+','B','B-','C+','C','D','F')),
    UNIQUE (student_id, course_id)
);

CREATE TABLE attendance (
    attendance_id    INT         PRIMARY KEY,
    student_id       BIGINT      NOT NULL,
    course_id        INT         NOT NULL REFERENCES courses(course_id),
    attendance_date  DATE        NOT NULL,
    status           VARCHAR(7)  NOT NULL CHECK (status IN ('Present', 'Absent'))
);

-- Lookup table: letter grade -> grade point (4.00 scale)
DROP TABLE IF EXISTS grade_points;
CREATE TABLE grade_points (
    grade  VARCHAR(2)   PRIMARY KEY,
    point  NUMERIC(3,2) NOT NULL
);
INSERT INTO grade_points VALUES
 ('A+',4.00),('A',3.75),('A-',3.50),('B+',3.25),('B',3.00),
 ('B-',2.75),('C+',2.50),('C',2.25),('D',2.00),('F',0.00);

-- Indexes for the most common joins
CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_grades_student      ON grades(student_id);
CREATE INDEX idx_attendance_student_course ON attendance(student_id, course_id);
