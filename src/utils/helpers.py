"""General utility helper functions."""

import re


def camel_to_snake(name: str) -> str:
    """
    Convert camelCase string to snake_case.

    Args:
        name: The camelCase string to convert

    Returns:
        The snake_case version of the string

    Examples:
        >>> camel_to_snake("proficiencyLevel")
        'proficiency_level'
        >>> camel_to_snake("tutorStyles")
        'tutor_styles'
    """
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
