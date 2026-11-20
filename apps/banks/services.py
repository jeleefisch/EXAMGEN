from core.generation.entities import CHOICE_COUNT, Question as CoreQuestion


def question_to_core(question):
    choices = list(question.choices.order_by('position'))
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


def bank_questions_to_core(bank):
    questions = bank.questions.filter(is_active=True).select_related('topic')
    return [question_to_core(question) for question in questions]
