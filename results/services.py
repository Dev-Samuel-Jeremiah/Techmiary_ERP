from cbt.models import ExamAttempt
from .models import TermResult, SessionResult

def update_term_result(attempt: ExamAttempt):
    """
    Update the term result for a student based on a completed ExamAttempt.
    """
    exam = attempt.exam_part.exam  # Corrected
    student = attempt.student

    # Get or create TermResult
    term_result, created = TermResult.objects.get_or_create(
        student=student,
        subject=exam.subject,
        session=exam.session,
        term=exam.term,
        class_assigned=student.class_assigned
    )

    # Assign score to the correct component
    if exam.exam_type == "CA1":
        term_result.ca1_score = attempt.score
    elif exam.exam_type == "CA2":
        term_result.ca2_score = attempt.score
    elif exam.exam_type == "EXAM":
        term_result.exam_score = attempt.score

    # Include essay score if available
    term_result.total_score = (
        (term_result.ca1_score or 0)
        + (term_result.ca2_score or 0)
        + (term_result.exam_score or 0)
        + (term_result.essay_score or 0)
    )
    term_result.save()


def generate_session_results(session):
    """
    Aggregate TermResults into SessionResults for a session.
    Reads all three terms and writes first_term / second_term / third_term,
    then saves each SessionResult so the cumulative page is always current.
    """
    results = TermResult.objects.filter(session=session).select_related('term', 'student', 'subject')

    for r in results:
        sr, _ = SessionResult.objects.get_or_create(
            student=r.student,
            subject=r.subject,
            session=session,
            class_assigned=r.class_assigned,
        )

        term_name = r.term.name.lower()
        if '1st' in term_name:
            sr.first_term = r.total_score
        elif '2nd' in term_name:
            sr.second_term = r.total_score
        elif '3rd' in term_name:
            sr.third_term = r.total_score

        # calculate() updates total_score & average_score but doesn't save — fix both
        sr.calculate()
        sr.save()