"""
Timetable Generator
===================
Greedy slot-filling scheduler with randomisation for variety.

Strategy:
  Instead of pure backtracking (which can hang indefinitely on large inputs),
  we use a greedy round-robin approach:
    1. Build a remaining_demand dict: {(class, subject, teacher): periods_left}
    2. Shuffle the order of (class, day, slot) cells.
    3. For each cell, pick the best valid assignment from remaining demand.
    4. Repeat with different shuffles until all demand is satisfied or timeout.

Constraints enforced:
  1. A teacher cannot teach two classes at the same time (same day+slot).
  2. A class cannot have two subjects at the same time (same day+slot).
  3. Each teacher-subject-class appears exactly `periods_per_week` times.
  4. No more than 2 periods of the same subject per class per day.
"""

import random
import time
from collections import defaultdict
from .models import (
    TimetableConfiguration, TeacherSubjectClass,
    GeneratedTimetable, TimetableSlot,
)


class TimetableGenerationError(Exception):
    pass


def generate_timetable(config_id: int, max_attempts: int = 30, timeout_seconds: int = 20) -> GeneratedTimetable:
    """
    Generate a timetable for the given TimetableConfiguration.

    Tries up to `max_attempts` greedy passes, each with a different random shuffle,
    but will stop after `timeout_seconds` regardless.

    Returns a saved (unpublished) GeneratedTimetable on success.
    Raises TimetableGenerationError with a clear message on failure.
    """
    config = TimetableConfiguration.objects.get(pk=config_id)
    slots = list(config.get_active_slots())
    days = config.active_days

    if not slots:
        raise TimetableGenerationError("No time slots configured (excluding breaks).")
    if not days:
        raise TimetableGenerationError("No active days configured.")

    assignments = list(
        config.teacher_subject_classes.select_related('staff', 'subject', 'school_class')
    )
    if not assignments:
        raise TimetableGenerationError(
            "No teacher-subject-class assignments found for this configuration. "
            "Please add assignments before generating."
        )

    # ------------------------------------------------------------------
    # Capacity pre-check (fast fail with a clear message)
    # ------------------------------------------------------------------
    total_cells = len(days) * len(slots)

    class_demand = defaultdict(int)
    class_names = {}
    for a in assignments:
        class_demand[a.school_class.pk] += a.periods_per_week
        class_names[a.school_class.pk] = a.school_class.name

    overloaded = []
    for cid, demand in class_demand.items():
        if demand > total_cells:
            overloaded.append(
                f"  • {class_names[cid]}: needs {demand} periods but only "
                f"{total_cells} slots available ({len(days)} days × {len(slots)} periods)"
            )
    if overloaded:
        raise TimetableGenerationError(
            "Cannot generate — the following classes exceed weekly capacity. "
            "Reduce periods_per_week or add more time slots/days.\n\n"
            + "\n".join(overloaded)
        )

    teacher_demand = defaultdict(int)
    teacher_names = {}
    for a in assignments:
        teacher_demand[a.staff.pk] += a.periods_per_week
        teacher_names[a.staff.pk] = a.staff.full_name

    overloaded_t = []
    for tid, demand in teacher_demand.items():
        if demand > total_cells:
            overloaded_t.append(
                f"  • {teacher_names[tid]}: assigned {demand} periods but only "
                f"{total_cells} slots available"
            )
    if overloaded_t:
        raise TimetableGenerationError(
            "Cannot generate — the following teachers exceed weekly capacity.\n\n"
            + "\n".join(overloaded_t)
        )

    # ------------------------------------------------------------------
    # Greedy generation with timeout
    # ------------------------------------------------------------------
    deadline = time.time() + timeout_seconds

    for attempt in range(max_attempts):
        if time.time() > deadline:
            break
        result = _greedy_attempt(assignments, slots, days, deadline)
        if result is not None:
            timetable = GeneratedTimetable.objects.create(config=config)
            bulk = [
                TimetableSlot(
                    timetable=timetable,
                    school_class=cls,
                    day=day,
                    time_slot=slot,
                    subject=subject,
                    teacher=teacher,
                )
                for (cls, day, slot), (subject, teacher) in result.items()
            ]
            TimetableSlot.objects.bulk_create(bulk)
            return timetable

    raise TimetableGenerationError(
        f"Could not generate a valid timetable within {timeout_seconds} seconds "
        f"after {max_attempts} attempts. "
        "Try: reducing periods_per_week, adding more time slots, or adding more days."
    )


# ---------------------------------------------------------------------------
# Internal greedy attempt
# ---------------------------------------------------------------------------

def _greedy_attempt(assignments, slots, days, deadline):
    """
    One greedy attempt. Returns schedule dict or None if it fails.

    Schedule dict: {(class_obj, day_str, slot_obj): (subject_obj, teacher_obj)}
    """
    # remaining[key] = periods still to place, where key = (class, subject, teacher)
    remaining = {}
    for a in assignments:
        key = (a.school_class, a.subject, a.staff)
        remaining[key] = a.periods_per_week

    # Tracking sets for constraint checking
    teacher_busy = defaultdict(set)   # teacher.pk → set of (day, slot.pk)
    class_busy   = defaultdict(set)   # class.pk   → set of (day, slot.pk)
    day_subj_count = defaultdict(int) # (class.pk, day, subject.pk) → count

    schedule = {}

    # Build all cells and shuffle
    all_cells = [(cls, day, slot)
                 for (cls, _, _) in remaining
                 for day in days
                 for slot in slots]
    # Deduplicate — we only need (class, day, slot) unique combos
    seen = set()
    cells = []
    for cls, day, slot in all_cells:
        key = (cls.pk, day, slot.pk)
        if key not in seen:
            seen.add(key)
            cells.append((cls, day, slot))

    random.shuffle(cells)

    # Sort assignments by most-constrained first (fewest periods = harder to place)
    assignment_keys = list(remaining.keys())

    for cls, day, slot in cells:
        if time.time() > deadline:
            return None

        cls_id = cls.pk
        slot_id = slot.pk

        # Skip if class already has a subject in this slot
        if (day, slot_id) in class_busy[cls_id]:
            continue

        # Collect candidates: assignments for this class with remaining demand
        candidates = [
            (cls2, subj, teacher)
            for (cls2, subj, teacher), left in remaining.items()
            if cls2.pk == cls_id and left > 0
        ]

        if not candidates:
            continue

        # Shuffle candidates for variety
        random.shuffle(candidates)

        placed = False
        for cls2, subj, teacher in candidates:
            teacher_id = teacher.pk
            subj_id = subj.pk

            # Teacher already busy this slot?
            if (day, slot_id) in teacher_busy[teacher_id]:
                continue

            # Already 2 of this subject today for this class?
            if day_subj_count[(cls_id, day, subj_id)] >= 2:
                continue

            # Place it
            schedule[(cls, day, slot)] = (subj, teacher)
            class_busy[cls_id].add((day, slot_id))
            teacher_busy[teacher_id].add((day, slot_id))
            day_subj_count[(cls_id, day, subj_id)] += 1
            remaining[(cls2, subj, teacher)] -= 1
            placed = True
            break

    # Check if all demand was satisfied
    if any(v > 0 for v in remaining.values()):
        return None  # not all periods placed

    return schedule
