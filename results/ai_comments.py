"""
results/ai_comments.py
─────────────────────────────────
AI comment generation for student term results using the Google Gemini API.

Generates three distinct comments per student per term:
  • teacher_comment   — class teacher's end-of-term remark
  • hos_comment       — Head of School's formal remark
  • overall_summary   — brief holistic summary of the student's performance

Requirements:
    pip install google-genai

Settings (.env and settings.py):
    GEMINI_API_KEY=AIza...
"""

import json
import logging

from google import genai
from google.genai import types
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Model constants ───────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash-lite"  # ← correct current model name
MAX_TOKENS   = 700
TEMPERATURE  = 0.9


def _performance_label(percentage: float) -> str:
    if percentage >= 80: return "Excellent"
    if percentage >= 70: return "Very Good"
    if percentage >= 60: return "Good"
    if percentage >= 50: return "Average"
    if percentage >= 40: return "Below Average"
    return "Poor"


def _grade_distribution(results) -> dict:
    dist = {}
    for r in results:
        grade = getattr(r, 'grade', '') or 'N/A'
        dist[grade] = dist.get(grade, 0) + 1
    return dist


def _strongest_weakest(results):
    valid = [r for r in results if not getattr(r, 'is_not_offering', False)]
    if not valid:
        return None, None
    strongest = max(valid, key=lambda r: r.total_score or 0)
    weakest   = min(valid, key=lambda r: r.total_score or 0)
    return (
        str(strongest.subject),
        str(weakest.subject) if weakest.subject != strongest.subject else None,
    )


def _build_prompt(student, term, session, results, overall_percentage: float) -> str:
    perf_label         = _performance_label(overall_percentage)
    grade_dist         = _grade_distribution(results)
    strongest, weakest = _strongest_weakest(results)
    gender             = getattr(student, 'gender', '') or 'the student'
    first_name         = (student.full_name or '').split()[0] if student.full_name else 'the student'

    subject_lines = []
    for r in results:
        if getattr(r, 'is_not_offering', False):
            continue
        subject_lines.append(
            f"  - {r.subject}: {int(round(r.total_score or 0))}/100 (Grade: {r.grade or 'N/A'})"
        )
    subject_table = "\n".join(subject_lines) if subject_lines else "  No results recorded."
    grade_summary = ", ".join(f"{c}x {g}" for g, c in sorted(grade_dist.items())) or "N/A"
    strongest_line = f"Strongest subject: {strongest}" if strongest else ""
    weakest_line   = f"Needs most attention: {weakest}" if weakest else ""

    pronoun_sub = "He"  if gender == "Male" else ("She"  if gender == "Female" else "They")
    pronoun_obj = "him" if gender == "Male" else ("her"  if gender == "Female" else "them")
    pronoun_pos = "his" if gender == "Male" else ("her"  if gender == "Female" else "their")

    return f"""You are an experienced Nigerian school report writer generating professional, \
personalised end-of-term comments for a student result card.

STUDENT
Name: {student.full_name} | First name: {first_name} | Gender: {gender}
Term: {term} | Session: {session} | Class: {student.class_assigned}

PERFORMANCE
Overall: {overall_percentage:.1f}% ({perf_label}) | Subjects: {len(results)}
Grades: {grade_summary}
{strongest_line}
{weakest_line}

Subjects:
{subject_table}

Pronouns: subject={pronoun_sub}, object={pronoun_obj}, possessive={pronoun_pos}

TASK: Return ONLY a valid JSON object with no preamble, no markdown fences, no extra text.

{{
  "teacher_comment": "...",
  "hos_comment": "...",
  "overall_summary": "..."
}}

RULES:
teacher_comment (2-3 sentences, max 60 words):
- Class teacher writing to parent/guardian
- Acknowledge performance, mention {pronoun_pos} strongest area
- End with encouragement or specific advice
- Use the student first name at least once, warm and personal tone

hos_comment (1-2 sentences, max 40 words):
- Head of School / Principal voice
- Formal, brief, authoritative, motivational
- Reference overall performance level
- Must NOT repeat teacher_comment wording

overall_summary (1 sentence, max 20 words):
- Concise holistic assessment for report card summary box
- Factual and positive

IMPORTANT: Sound human-written, vary sentence structure, Nigerian context (this term, promotion, new session).
"""


def generate_comments_for_student(student, term, session, results,
                                   overall_percentage: float = 0.0):
    """
    Generate and persist AI comments for one student.
    Returns AIStudentComment instance. Never raises.
    """
    from results.models import AIStudentComment

    prompt = _build_prompt(student, term, session, results, overall_percentage)

    teacher_comment = ''
    hos_comment     = ''
    overall_summary = ''
    generation_ok   = False
    error_message   = ''
    raw_text        = ''

    try:
        api_key = (
            getattr(settings, 'GEMINI_API_KEY', None)
            or getattr(settings, 'OPENAI_API_KEY', None)
        )
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Add GEMINI_API_KEY=AIza... to your .env and "
                "GEMINI_API_KEY = config('GEMINI_API_KEY') to settings.py."
            )

        # New google-genai SDK (replaces deprecated google-generativeai)
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            ),
        )

        raw_text = response.text.strip()

        # Strip markdown fences if Gemini wraps in ```json ... ```
        if raw_text.startswith("```"):
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        data = json.loads(raw_text)
        teacher_comment = str(data.get('teacher_comment', '')).strip()
        hos_comment     = str(data.get('hos_comment',     '')).strip()
        overall_summary = str(data.get('overall_summary', '')).strip()

        if not teacher_comment:
            raise ValueError("Gemini returned an empty teacher_comment.")

        generation_ok = True
        logger.info(
            "AI comments generated for student=%s term=%s session=%s (%.1f%%)",
            student.full_name, term, session, overall_percentage
        )

    except json.JSONDecodeError as e:
        error_message = f"JSON parse error: {e}. Raw: {raw_text[:200]}"
        logger.error("AI comment JSON error for student %s: %s", student.id, error_message)

    except Exception as e:
        error_message = str(e)
        logger.error("AI comment failed for student %s: %s", student.id, e, exc_info=True)

    obj, _ = AIStudentComment.objects.update_or_create(
        student=student,
        term=term,
        session=session,
        defaults={
            'teacher_comment':    teacher_comment,
            'hos_comment':        hos_comment,
            'overall_summary':    overall_summary,
            'overall_percentage': overall_percentage,
            'total_subjects':     len([r for r in results
                                       if not getattr(r, 'is_not_offering', False)]),
            'generated_at':       timezone.now(),
            'model_used':         GEMINI_MODEL,
            'generation_ok':      generation_ok,
            'error_message':      error_message,
        },
    )
    return obj


def generate_comments_for_class(class_obj, term, session) -> dict:
    """Generate AI comments for every active student in a class."""
    from users.models import Student
    from results.models import TermResult

    students = Student.objects.filter(
        class_assigned=class_obj, status='Active',
    ).order_by('full_name')

    summary = {'total': 0, 'success': 0, 'failed': 0, 'errors': []}

    for student in students:
        summary['total'] += 1
        results = list(
            TermResult.objects.filter(
                student=student, term=term, session=session,
            ).select_related('subject')
        )
        results = [r for r in results if not getattr(r, 'is_not_offering', False)]

        total_obtained   = sum(r.total_score or 0 for r in results)
        total_obtainable = len(results) * 100
        overall_pct = round((total_obtained / total_obtainable) * 100, 1) if total_obtainable else 0.0

        obj = generate_comments_for_student(student, term, session, results, overall_pct)

        if obj.generation_ok:
            summary['success'] += 1
        else:
            summary['failed'] += 1
            summary['errors'].append(f"{student.full_name}: {obj.error_message}")

    logger.info(
        "Bulk AI generation complete — class=%s term=%s: %d/%d succeeded",
        class_obj, term, summary['success'], summary['total']
    )
    return summary