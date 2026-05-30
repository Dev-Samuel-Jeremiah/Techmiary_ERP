from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    # ── Staff / Admin ──────────────────────────────────────────────────
    path('term/',             views.term_results,                  name='term_results'),
    path('manual-scores/',    views.manual_score_entry,            name='manual_score_entry'),
    path('cbt-scores/',       views.cbt_scores_reference,          name='cbt_scores_reference'),
    path('cumulative/',       views.cumulative_results,            name='cumulative_results'),
    path('generate-session/', views.generate_session_results_view, name='generate_session_results'),
    path('publish-results/',  views.publish_results_page,          name='publish_results_page'),
    path('batch-results/',    views.batch_results,                 name='batch_results'),

    # ── Parent ─────────────────────────────────────────────────────────
    path('dashboard/',        views.parent_view_results, name='dashboard'),
    path(
        'results/<int:student_id>/<int:session_id>/<int:term_id>/',
        views.parent_result_detail,
        name='result_detail',
    ),

    # ── Student ────────────────────────────────────────────────────────
    path(
        'results/<int:session_id>/<int:term_id>/',
        views.student_result_detail,
        name='student_result_detail',
    ),

    # ── AJAX / autosave endpoints ──────────────────────────────────────
    path('save-teacher-remark/',   views.save_teacher_remark,   name='save_teacher_remark'),
    path('save-subject-remark/',   views.save_subject_remark,   name='save_subject_remark'),
    path('save-hos-remark/',       views.save_hos_remark,       name='save_hos_remark'),
    path('save-skill-assessment/', views.save_skill_assessment, name='save_skill_assessment'),
    path('attendance/',            views.manual_term_attendance, name='manual_term_attendance'),

    # ── AI Comment endpoints ───────────────────────────────────────────
    # Single student — called from the result card page
    path('ai-comment/generate/',      views.generate_ai_comment,        name='generate_ai_comment'),
    # Whole class bulk generation — called from an admin/class management page
    path('ai-comment/generate-bulk/', views.generate_ai_comments_bulk,  name='generate_ai_comments_bulk'),
    # GET existing comment to prefill on page load
    path('ai-comment/get/',           views.get_ai_comment,             name='get_ai_comment'),
]