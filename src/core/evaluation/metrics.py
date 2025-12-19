"""Custom DeepEval metrics for English tutoring conversation quality.

These metrics evaluate:
1. Topic Adherence - Does the tutor stay on the learning topic?
2. Engagement - Is the conversation engaging and encouraging?
3. Learning Effectiveness - Does the tutor help the student learn?

Usage:
    from core.evaluation.metrics import TopicAdherenceMetric

    metric = TopicAdherenceMetric()
    score = metric.measure(test_case)
"""

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams


class TopicAdherenceMetric(GEval):
    """
    Evaluates whether the tutor stays on the English learning topic.

    Checks:
    - Responses relate to English language learning
    - Tutor doesn't go off-topic into unrelated subjects
    - Conversation maintains focus on student's learning goals
    """

    def __init__(self, threshold: float = 0.7):
        super().__init__(
            name="Topic Adherence",
            criteria=(
                "Evaluate whether the English tutor stays focused on the "
                "learning topic throughout the conversation. The tutor should "
                "keep discussions relevant to English language learning, "
                "vocabulary, grammar, pronunciation, or conversation practice."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            evaluation_steps=[
                "Check if each tutor response relates to English learning",
                "Verify the tutor doesn't drift into unrelated topics",
                "Assess if corrections and feedback are language-focused",
                "Confirm the conversation serves the student's learning goals",
            ],
            threshold=threshold,
        )


class EngagementMetric(GEval):
    """
    Evaluates how engaging and encouraging the tutor is.

    Checks:
    - Tutor uses encouraging language
    - Conversation feels natural and supportive
    - Student is motivated to continue practicing
    """

    def __init__(self, threshold: float = 0.7):
        super().__init__(
            name="Engagement",
            criteria=(
                "Evaluate how engaging and encouraging the English tutor is. "
                "A good tutor should create a supportive learning environment, "
                "use positive reinforcement, ask engaging questions, and make "
                "the student feel comfortable making mistakes."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            evaluation_steps=[
                "Check if the tutor uses encouraging and supportive language",
                "Verify the tutor acknowledges student efforts positively",
                "Assess if the tutor asks engaging follow-up questions",
                "Confirm the conversation tone is warm and non-judgmental",
                "Check if mistakes are treated as learning opportunities",
            ],
            threshold=threshold,
        )


class LearningEffectivenessMetric(GEval):
    """
    Evaluates whether the tutoring session helps the student learn.

    Checks:
    - Tutor provides clear explanations
    - Corrections are helpful and educational
    - Student's proficiency level is respected
    - Feedback is actionable
    """

    def __init__(self, threshold: float = 0.7):
        super().__init__(
            name="Learning Effectiveness",
            criteria=(
                "Evaluate whether the tutoring session effectively helps the "
                "student improve their English. The tutor should provide clear "
                "explanations, give constructive feedback, adapt to the student's "
                "proficiency level, and offer actionable suggestions for improvement."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            evaluation_steps=[
                "Check if explanations are clear and understandable",
                "Verify corrections include helpful context or examples",
                "Assess if vocabulary/grammar is appropriate for student level",
                "Confirm feedback is specific and actionable",
                "Check if the tutor scaffolds learning progressively",
            ],
            threshold=threshold,
        )


class RoleAdherenceMetric(GEval):
    """
    Evaluates whether the tutor stays in character as an English tutor.

    Checks:
    - Maintains tutor persona consistently
    - Doesn't break character or become confused about role
    - Appropriate professional boundaries
    """

    def __init__(self, threshold: float = 0.8):
        super().__init__(
            name="Role Adherence",
            criteria=(
                "Evaluate whether the AI consistently maintains its role as an "
                "English language tutor throughout the conversation. The tutor "
                "should not break character, claim to be something else, or "
                "behave inappropriately for a teaching context."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            evaluation_steps=[
                "Check if the tutor maintains consistent persona",
                "Verify no instances of breaking character",
                "Assess if responses are appropriate for a teaching context",
                "Confirm the tutor doesn't claim capabilities outside its role",
            ],
            threshold=threshold,
        )


class ConversationCompletenessMetric(GEval):
    """
    Evaluates whether the conversation addresses the student's needs.

    Checks:
    - Student's questions are answered
    - Learning objectives are addressed
    - Session has a logical flow and conclusion
    """

    def __init__(self, threshold: float = 0.7):
        super().__init__(
            name="Conversation Completeness",
            criteria=(
                "Evaluate whether the tutoring conversation adequately addresses "
                "the student's learning needs. The tutor should answer questions "
                "fully, address stated learning objectives, and provide a complete "
                "learning experience rather than leaving topics unfinished."
            ),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
            ],
            evaluation_steps=[
                "Check if student questions are answered completely",
                "Verify learning objectives mentioned are addressed",
                "Assess if topics introduced are properly concluded",
                "Confirm no important points are left hanging",
            ],
            threshold=threshold,
        )
