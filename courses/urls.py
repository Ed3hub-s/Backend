from django.urls import path
from .views import (
    CategoryListView, CourseListView, CourseDetailView, EnrolledCourseDetailView,
    EducatorCourseListView, CourseCreateView, CourseUpdateView,
    LessonDetailView,
    EnrollView, MyEnrollmentsView,
    CompleteLessonView, CompleteModuleView,
    CourseReviewView,
    MyWalletView, ClaimTokenView, MyStatsView,
    IssueCertificateView, MyCertificatesView, CertificateDetailView, RegenerateCertificateView,
    ModuleCreateView, ModuleUpdateView,
    LessonCreateView, LessonUpdateView,
    QuizCreateView, QuizUpdateView,
    AssessmentCreateView, AssessmentUpdateView,
    CourseContentView,
    SessionListCreateView, SessionDetailView, PublicSessionListView,
    SessionRegisterView, SessionUnregisterView,
)

urlpatterns = [
    # Catalogue
    path('categories/', CategoryListView.as_view(), name='categories'),
    path('', CourseListView.as_view(), name='course-list'),

    # Educator course management
    path('my/courses/', EducatorCourseListView.as_view(), name='educator-courses'),
    path('create/', CourseCreateView.as_view(), name='course-create'),
    path('<int:course_id>/update/', CourseUpdateView.as_view(), name='course-update'),
    path('<int:course_id>/content/', CourseContentView.as_view(), name='course-content'),

    # Modules
    path('<int:course_id>/modules/create/', ModuleCreateView.as_view(), name='module-create'),
    path('modules/<int:module_id>/', ModuleUpdateView.as_view(), name='module-update'),
    path('modules/<int:module_id>/complete/', CompleteModuleView.as_view(), name='complete-module'),

    # Lessons
    path('modules/<int:module_id>/lessons/create/', LessonCreateView.as_view(), name='lesson-create'),
    path('lessons/<int:lesson_id>/', LessonUpdateView.as_view(), name='lesson-update'),
    path('lessons/<int:lesson_id>/complete/', CompleteLessonView.as_view(), name='complete-lesson'),

    # Quizzes
    path('modules/<int:module_id>/quiz/create/', QuizCreateView.as_view(), name='quiz-create'),
    path('quizzes/<int:quiz_id>/', QuizUpdateView.as_view(), name='quiz-update'),

    # Assessments
    path('<int:course_id>/assessments/create/', AssessmentCreateView.as_view(), name='assessment-create'),
    path('assessments/<int:assessment_id>/', AssessmentUpdateView.as_view(), name='assessment-update'),

    # Enrollment
    path('my/enrollments/', MyEnrollmentsView.as_view(), name='my-enrollments'),
    path('my/stats/', MyStatsView.as_view(), name='my-stats'),
    path('enrolled/<int:course_id>/', EnrolledCourseDetailView.as_view(), name='enrolled-course-detail'),

    # Reviews
    path('<int:course_id>/review/', CourseReviewView.as_view(), name='course-review'),

    # Wallet & Tokens
    path('wallet/me/', MyWalletView.as_view(), name='my-wallet'),
    path('wallet/claim/<int:transaction_id>/', ClaimTokenView.as_view(), name='claim-token'),

    # Certificates
    path('my/certificates/', MyCertificatesView.as_view(), name='my-certificates'),
    path('my/certificate/<int:enrollment_id>/', IssueCertificateView.as_view(), name='issue-certificate'),
    path('certificates/<str:certificate_id>/regenerate/', RegenerateCertificateView.as_view(), name='certificate-regenerate'),
    path('certificates/<str:certificate_id>/', CertificateDetailView.as_view(), name='certificate-detail'),

    # Sessions
    path('sessions/', SessionListCreateView.as_view(), name='session-list-create'),
    path('sessions/public/', PublicSessionListView.as_view(), name='public-sessions'),
    path('sessions/<int:session_id>/', SessionDetailView.as_view(), name='session-detail'),
    path('sessions/<int:session_id>/register/', SessionRegisterView.as_view(), name='session-register'),
    path('sessions/<int:session_id>/unregister/', SessionUnregisterView.as_view(), name='session-unregister'),

    # Course detail + enroll (keep last to avoid slug conflicts)
    path('<int:course_id>/enroll/', EnrollView.as_view(), name='enroll'),
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail'),
]
