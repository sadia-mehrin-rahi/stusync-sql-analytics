# StuSync Power BI Dashboard: ধাপে ধাপে গাইড

মোট সময়: ১ থেকে ১.৫ ঘণ্টা। শেষে একটা পেজের dashboard হবে:

```
┌──────────────────────────────────────────────────────────────────────┐
│ StuSync Academic Dashboard                          [Department ▼]   │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────┤
│  Students    │  CGPA        │  Fail Rate   │  At-Risk     │ Attend.  │
│    400       │   2.93       │   5.0%       │   207        │  82.4%   │
├──────────────────────────────────┬───────────────────────────────────┤
│  CGPA by department (bar)        │  Fail rate by attendance (column) │
│                                  │    75% or more  vs  Below 75%     │
├──────────────────────────────────┼───────────────────────────────────┤
│  Attendance vs CGPA (scatter,    │  At-risk students (table)         │
│  one dot per student)            │  name · course · attendance · grade│
└──────────────────────────────────┴───────────────────────────────────┘
```

---

## ধাপ ০: Install
Microsoft Store খোলো → **Power BI Desktop** খোঁজো → Get/Install। এটা free।

## ধাপ ১: Database-এ view দুটো বানাও (একবারই করতে হবে)
pgAdmin → `stusync` database-এ right-click → Query Tool → Open File → `sql\04_powerbi_views.sql` → **F5**।
এতে `vw_course_results` আর `vw_student_summary` নামে দুইটা view তৈরি হবে।

## ধাপ ২: Data আনো
Power BI Desktop খোলো → **Blank report** → Home → **Get data** → More… → **PostgreSQL database** → Connect।
- Server: `localhost`
- Database: `stusync`
- Data Connectivity mode: **Import**
- OK চাপো। User name `postgres` আর তোমার password দিয়ে Connect করো।
- তালিকা থেকে **`public.vw_course_results`** আর **`public.vw_student_summary`**-এ টিক দাও → **Load**।

> **PostgreSQL connect না হলে (driver error):** Get data → **Text/CSV** → `powerbi\data\vw_course_results.csv` → Load। একইভাবে `vw_student_summary.csv`-ও load করো। বাকি সব ধাপ একই থাকবে।

## ধাপ ৩: Relationship ঠিক আছে কিনা দেখো
বাম পাশে **Model view** আইকনে (তৃতীয়টা) যাও। দুই table-এর `student_id`-এর মধ্যে একটা লাইন থাকা উচিত।
না থাকলে `vw_student_summary[student_id]` টেনে এনে `vw_course_results[student_id]`-এর উপর ছেড়ে দাও। এতে **One-to-many** relationship হবে।

## ধাপ ৪: Theme লাগাও
**View** tab → Themes-এর ড্রপডাউন → **Browse for themes** → `powerbi\StuSync_theme.json`।

## ধাপ ৫: Measure বানাও
ডান পাশের Data pane-এ **vw_course_results** select করো → Home → **New measure**।
`powerbi\DAX_measures.txt` থেকে একটা একটা measure copy-paste করে Enter চাপো। মোট ৬টা।
প্রতিটা measure-এর format ঠিক করো (Measure tools tab থেকে): Fail Rate আর Avg Attendance % হবে **Percentage**, বাকিগুলো **2 decimal**।

## ধাপ ৬: Visual বানাও
বাম পাশে **Report view**-এ ফিরে এসো। প্রতিটা visual-এর জন্য ডান দিকের **Visualizations** pane থেকে আইকনে click করো, তারপর Data pane থেকে field টেনে আনো।

| # | Visual | কী টেনে আনবে |
|---|---|---|
| 1 | **Card** ×5 | একটা card-এ একটা করে measure: `Students`, `CGPA (credit weighted)`, `Fail Rate`, `At-Risk Results`, `Avg Attendance %` |
| 2 | **Clustered bar chart** | Y-axis: `department` · X-axis: `CGPA (credit weighted)` |
| 3 | **Clustered column chart** | X-axis: `attendance_band` · Y-axis: `Fail Rate` |
| 4 | **Scatter chart** | Values: `vw_student_summary[student_id]` · X-axis: `avg_attendance_pct` · Y-axis: `cgpa` · Legend: `department` |
| 5 | **Table** | `name`, `department`, `course_name`, `attendance_pct`, `grade`। তারপর Filters pane-এ **is_at_risk = True** করো (নিচে দেখো) |
| 6 | **Slicer** | `department`। Format → Slicer settings → Style: **Dropdown** |

**Table-এ filter দেওয়ার নিয়ম:** Table visual select করো → ডান দিকে **Filters** pane → "Filters on this visual"-এ `is_at_risk` টেনে আনো → **True**-তে টিক দাও।

**Title দেওয়ার নিয়ম:** Visual select করো → Format (তুলির আইকন) → General → Title → লেখা বদলাও।
উপরে বাম দিকে Insert → **Text box** দিয়ে লেখো: *StuSync Academic Dashboard*।

## ধাপ ৭: সংখ্যা মিলিয়ে দেখো
Department slicer-এ কিছু select না থাকলে সংখ্যাগুলো এরকম হওয়ার কথা:
Students **400** · CGPA **2.93** · Fail Rate **5.0%** · At-Risk **207** · Attendance **82.4%**।
Fail rate chart-এ দেখাবে: 75% or more → **1.0%**, Below 75% → **20.6%**।

মিললে বুঝবে measure-গুলো ঠিক আছে। এবার slicer থেকে CSE select করে দেখো, সব visual একসাথে বদলায় কিনা।

## ধাপ ৮: Save আর GitHub
1. File → Save As → `powerbi\StuSync_Dashboard.pbix`।
2. Dashboard-এর একটা screenshot নাও (Win + Shift + S) → `powerbi\dashboard.png` নামে save করো।
3. GitHub-এ push করো:
   ```
   git add .
   git commit -m "Add Power BI dashboard"
   git push
   ```

README-তে screenshot দেখানোর লাইন আগে থেকেই আছে। `dashboard.png` রাখলেই GitHub-এ ছবিটা দেখা যাবে।
