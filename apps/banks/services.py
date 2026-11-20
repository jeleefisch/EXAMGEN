from core.generation.entities import CHOICE_COUNT, Question as CoreQuestion


def question_to_core(question):
    # Sort in Python so prefetched choices are used (no extra query per question).
    choices = sorted(question.choices.all(), key=lambda choice: choice.position)
    correct_choices = [choice for choice in choices if choice.is_correct]
    expected = CHOICE_COUNT[question.qtype]

    if len(choices) != expected:
        raise ValueError(
            f'Question {question.pk} requires exactly {expected} choices.'
        )
    if len(correct_choices) != 1:
        raise ValueError(
            f'Question {question.pk} requires exactly one correct choice.'
        )

    correct_index = choices.index(correct_choices[0])
    return CoreQuestion(
        id=question.pk,
        topic=question.topic.name,
        difficulty=question.difficulty,
        qtype=question.qtype,
        n_choices=expected,
        correct_index=correct_index,
    )


def _active_questions(bank):
    return (
        bank.questions.filter(is_active=True)
        .select_related('topic')
        .prefetch_related('choices')
    )


def bank_questions_to_core(bank):
    """All active questions as engine objects. Raises on the first invalid one."""
    return [question_to_core(question) for question in _active_questions(bank)]


def eligible_core_questions(bank):
    """Active questions as engine objects, plus the ones that had to be left out.

    Returns (usable, excluded) where excluded is a list of (question_pk, reason).
    Use this when building an exam, so one broken question does not block it.
    """
    usable, excluded = [], []
    for question in _active_questions(bank):
        try:
            usable.append(question_to_core(question))
        except ValueError as error:
            excluded.append((question.pk, str(error)))
    return usable, excluded