# Complete Course Upload Flow - Visual Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EDUCATOR INTERFACE                        │
│                    (React/TypeScript Frontend)                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ HTTP/REST API
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DJANGO BACKEND API                          │
│                    (Python/Django REST Framework)                │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 │ ORM
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      POSTGRESQL DATABASE                         │
│              (Course, Module, Lesson, Quiz, Assessment)          │
└─────────────────────────────────────────────────────────────────┘
```

## Course Creation Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 1: COURSE DETAILS                                               │
├──────────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ • Course Title                                                 │   │
│ │ • What You'll Learn                                            │   │
│ │ • Ideal For                                                    │   │
│ │ • Skill Level (Beginner/Intermediate/Advanced/All Levels)     │   │
│ │ • Tools Used                                                   │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│                           [Next Button] ──────────────────────────┐   │
└──────────────────────────────────────────────────────────────────│───┘
                                                                    │
                                                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 2: COURSE STRUCTURE                                             │
├──────────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ Course Description                                             │   │
│ │ What's Included                                                │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ MODULES                                    [Add Module Button] │   │
│ │ ┌──────────────────────────────────────────────────────────┐   │   │
│ │ │ Module 1: Introduction                    [Edit] [Delete]│   │   │
│ │ │ 📚 3 Lessons  📝 2 Quizzes  ✅ 1 Assessment              │   │   │
│ │ │ ┌────────────────────────────────────────────────────┐   │   │   │
│ │ │ │ Lessons:                                           │   │   │   │
│ │ │ │ 🎥 Video: What is a DAO? (15 min)                 │   │   │   │
│ │ │ │ 📄 Text: History of DAOs                          │   │   │   │
│ │ │ │ 📎 Document: Case Studies.pdf                     │   │   │   │
│ │ │ └────────────────────────────────────────────────────┘   │   │   │
│ │ └──────────────────────────────────────────────────────────┘   │   │
│ │                                                                │   │
│ │ ┌──────────────────────────────────────────────────────────┐   │   │
│ │ │ Module 2: Governance                      [Edit] [Delete]│   │   │
│ │ │ 📚 4 Lessons  📝 2 Quizzes  ✅ 1 Assessment              │   │   │
│ │ └──────────────────────────────────────────────────────────┘   │   │
│ │                                                                │   │
│ │ Summary: 2 modules • 7 lessons • 4 quizzes • 2 assessments    │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ Course Thumbnail                                               │   │
│ │ [Click to upload image]                                        │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│                    [Back Button]  [Next Button] ──────────────────┐   │
└──────────────────────────────────────────────────────────────────│───┘
                                                                    │
                                                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ STEP 3: PRICING & DURATION                                           │
├──────────────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ Pricing                                                        │   │
│ │ ☐ Free course                                                  │   │
│ │ ₦ [Price Input]                                                │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ Duration                                                       │   │
│ │ Estimated Hours: [12]    Hours/Week: [3]                       │   │
│ │ Schedule Type: [Self-paced ▼]                                  │   │
│ │ Date Range: [Calendar Picker]                                  │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ ☑ Publish course immediately                                   │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│                    [Back Button]  [Save Course Button] ───────────┐   │
└──────────────────────────────────────────────────────────────────│───┘
                                                                    │
                                                                    ▼
                                                            [API Request]
```

## Module Builder Modal

```
┌────────────────────────────────────────────────────────────────────┐
│ Add Module                                                    [X]  │
├────────────────────────────────────────────────────────────────────┤
│ Module Title: [Understanding the Basics                        ]   │
│ Description:  [This module covers fundamental concepts...      ]   │
│                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ [Lessons (3)] [Quizzes (2)] [Assessments (1)]               │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ ┌─ LESSONS TAB ─────────────────────────────────────────────────┐  │
│ │ ┌────────────────────────────────────────────────────────┐   │  │
│ │ │ LESSON 1                                    [Delete 🗑] │   │  │
│ │ │ Title: [What is a DAO?                              ]   │   │  │
│ │ │ Type:  [Video ▼]    Duration: [15 min           ]   │   │  │
│ │ │ Video URL: [https://youtube.com/watch?v=...        ]   │   │  │
│ │ └────────────────────────────────────────────────────────┘   │  │
│ │                                                              │  │
│ │ ┌────────────────────────────────────────────────────────┐   │  │
│ │ │ LESSON 2                                    [Delete 🗑] │   │  │
│ │ │ Title: [History of DAOs                             ]   │   │  │
│ │ │ Type:  [Text Content ▼]  Duration: [10 min         ]   │   │  │
│ │ │ Content: [DAOs emerged in 2016 with The DAO...     ]   │   │  │
│ │ └────────────────────────────────────────────────────────┘   │  │
│ │                                                              │  │
│ │ [+ Add Lesson]                                               │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─ QUIZZES TAB ─────────────────────────────────────────────────┐  │
│ │ ┌────────────────────────────────────────────────────────┐   │  │
│ │ │ QUIZ 1                                      [Delete 🗑] │   │  │
│ │ │ Question: [What is the primary purpose of a DAO?   ]   │   │  │
│ │ │ Type: [Multiple Choice ▼]                           │   │   │  │
│ │ │ Options:                                             │   │   │  │
│ │ │   [A) Centralize control                         ]   │   │   │  │
│ │ │   [B) Decentralize governance                    ]   │   │   │  │
│ │ │   [C) Speed up transactions                      ]   │   │   │  │
│ │ │   [D) Store data                                 ]   │   │   │  │
│ │ │ Correct Answer: [B) Decentralize governance      ]   │   │   │  │
│ │ └────────────────────────────────────────────────────────┘   │  │
│ │                                                              │  │
│ │ [+ Add Quiz]                                                 │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│ ┌─ ASSESSMENTS TAB ─────────────────────────────────────────────┐  │
│ │ ┌────────────────────────────────────────────────────────┐   │  │
│ │ │ ASSESSMENT 1                                [Delete 🗑] │   │  │
│ │ │ Question: [Design a governance flow for a DAO      ]   │   │  │
│ │ │ Type: [Practical Application ▼]                     │   │   │  │
│ │ │ Expected Answer:                                     │   │   │  │
│ │ │ [Should include proposal creation, voting...       ]   │   │  │
│ │ └────────────────────────────────────────────────────────┘   │  │
│ │                                                              │  │
│ │ [+ Add Assessment]                                           │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│                    [Cancel]  [Save Module]                         │
└────────────────────────────────────────────────────────────────────┘
```

## Backend Data Processing

```
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND SENDS                                                  │
├─────────────────────────────────────────────────────────────────┤
│ FormData {                                                      │
│   title: "Introduction to DAOs"                                 │
│   description: "Learn about DAOs..."                            │
│   skill_level: "beginner"                                       │
│   price: "0"                                                    │
│   is_free: true                                                 │
│   thumbnail: [File]                                             │
│   modules: JSON.stringify([                                     │
│     {                                                           │
│       id: "1234567890",                                         │
│       title: "Module 1: DAO Basics",                            │
│       description: "Introduction to DAOs",                      │
│       lessons: [                                                │
│         {                                                       │
│           id: "1234567891",                                     │
│           title: "What is a DAO?",                              │
│           type: "video",                                        │
│           videoUrl: "https://youtube.com/...",                  │
│           duration: "15 min"                                    │
│         }                                                       │
│       ],                                                        │
│       quizzes: [                                                │
│         {                                                       │
│           id: "1234567892",                                     │
│           question: "What is a DAO?",                           │
│           type: "mcq",                                          │
│           options: ["A", "B", "C", "D"],                        │
│           correctAnswer: "B"                                    │
│         }                                                       │
│       ],                                                        │
│       assessments: [...]                                        │
│     }                                                           │
│   ])                                                            │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND PROCESSES                                               │
├─────────────────────────────────────────────────────────────────┤
│ 1. Validate course data with CourseWriteSerializer             │
│ 2. Create Course record                                         │
│ 3. Parse modules JSON                                           │
│ 4. For each module:                                             │
│    ├─ Create Module record (with order)                         │
│    ├─ For each lesson:                                          │
│    │  └─ Create Lesson record (map types, parse duration)       │
│    ├─ If quizzes exist:                                         │
│    │  ├─ Create Quiz record                                     │
│    │  └─ For each quiz:                                         │
│    │     ├─ Create Question record                              │
│    │     └─ Create Choice records (mark correct)                │
│    └─ For each assessment:                                      │
│       └─ Create Assessment record                               │
│ 5. Return success response                                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ DATABASE STRUCTURE                                              │
├─────────────────────────────────────────────────────────────────┤
│ Course (id=1)                                                   │
│ ├─ title: "Introduction to DAOs"                                │
│ ├─ instructor_id: 5                                             │
│ ├─ skill_level: "beginner"                                      │
│ └─ ...                                                          │
│                                                                 │
│ Module (id=1, course_id=1, order=1)                             │
│ ├─ title: "Module 1: DAO Basics"                                │
│ └─ reward_tokens: 10                                            │
│                                                                 │
│ Lesson (id=1, module_id=1, order=1)                             │
│ ├─ title: "What is a DAO?"                                      │
│ ├─ lesson_type: "video"                                         │
│ ├─ video_url: "https://youtube.com/..."                         │
│ └─ duration_minutes: 15                                         │
│                                                                 │
│ Quiz (id=1, module_id=1)                                        │
│ ├─ title: "Module 1: DAO Basics Quiz"                           │
│ ├─ pass_score: 70                                               │
│ └─ reward_tokens: 5                                             │
│                                                                 │
│ Question (id=1, quiz_id=1, order=1)                             │
│ └─ text: "What is a DAO?"                                       │
│                                                                 │
│ Choice (id=1, question_id=1, is_correct=false)                  │
│ └─ text: "A) Centralize control"                                │
│                                                                 │
│ Choice (id=2, question_id=1, is_correct=true)                   │
│ └─ text: "B) Decentralize governance"                           │
│                                                                 │
│ Assessment (id=1, course_id=1, module_id=1)                     │
│ ├─ title: "Design a governance flow"                            │
│ ├─ description: "Expected: proposal creation..."                │
│ └─ reward_tokens: 15                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Student Learning Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ STUDENT ENROLLS IN COURSE                                       │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ COURSE DASHBOARD                                                │
├─────────────────────────────────────────────────────────────────┤
│ Module 1: DAO Basics                                            │
│ ├─ ☐ Lesson 1: What is a DAO? (15 min)                          │
│ ├─ ☐ Lesson 2: History of DAOs (10 min)                         │
│ ├─ ☐ Quiz: Module 1 Quiz                                        │
│ └─ ☐ Assessment: Design a governance flow                       │
│                                                                 │
│ Module 2: Governance                                            │
│ ├─ 🔒 Lesson 1: Voting Mechanisms (locked)                      │
│ └─ ...                                                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STUDENT COMPLETES LESSON                                        │
│ POST /api/courses/lessons/{lesson_id}/complete/                 │
│ → LessonProgress created (completed=true)                       │
│ → Enrollment.progress_percent updated                           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STUDENT TAKES QUIZ                                              │
│ → Answers submitted                                             │
│ → Auto-graded against correct answers                           │
│ → If pass_score met:                                            │
│   ├─ TokenTransaction created (+5 tokens)                       │
│   └─ Student can claim tokens                                   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STUDENT SUBMITS ASSESSMENT                                      │
│ → Submission stored                                             │
│ → Educator grades manually                                      │
│ → If passed:                                                    │
│   ├─ TokenTransaction created (+15 tokens)                      │
│   └─ Student can claim tokens                                   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STUDENT COMPLETES MODULE                                        │
│ POST /api/courses/modules/{module_id}/complete/                 │
│ → ModuleProgress created (completed=true)                       │
│ → TokenTransaction created (+10 tokens)                         │
│ → Next module unlocked                                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STUDENT COMPLETES COURSE                                        │
│ → Enrollment.completed = true                                   │
│ → TokenTransaction created (+10 tokens)                         │
│ → Certificate issued                                            │
│ → Student can mint NFT certificate (optional)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Token Flow

```
Action                    Tokens    Total
─────────────────────────────────────────
Complete Module 1         +10       10
Pass Module 1 Quiz        +5        15
Pass Module 1 Assessment  +15       30
Complete Module 2         +10       40
Pass Module 2 Quiz        +5        45
Pass Module 2 Assessment  +15       60
Complete Course           +10       70
─────────────────────────────────────────
Total Earned                        70 🏆
```

## File Structure

```
Frontend/
├── src/
│   ├── creators_dashboard_components/
│   │   └── upload_courses/
│   │       └── UploadCourses.tsx ✅ ENHANCED
│   └── lib/
│       └── api.ts
├── EDUCATORS_UPLOAD_GUIDE.md ✅ NEW
├── UPLOAD_FEATURES_SUMMARY.md ✅ NEW
├── BACKEND_INTEGRATION_GUIDE.md ✅ NEW
└── QUICK_START_EDUCATORS.md ✅ NEW

Backend/
└── courses/
    ├── models.py ✅ EXISTING (comprehensive)
    ├── serializers.py ✅ EXISTING
    ├── views.py ✅ ENHANCED (CourseCreateView, CourseUpdateView)
    └── urls.py ✅ EXISTING

Root/
└── IMPLEMENTATION_SUMMARY.md ✅ NEW
```

This visual guide shows the complete flow from educator creating a course to student earning tokens and certificates!
