"""Validate the decision wire contract before a model answer can affect a proposal."""
import argparse
import math


def score(value):
    if isinstance(value, bool):
        raise ValueError("a score must be numeric")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("a score must be numeric") from None
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("a score must be finite and between zero and one")
    return value


def threshold(value):
    try:
        return score(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def parse_answer(response, key, options, *, allow_direct=False, infer_choice=False):
    """Unreadable answers abstain. Unknown probability keys never become choices."""
    if not isinstance(response, dict):
        return None, 0.0, {}
    answers = response.get("answers", response if allow_direct else {})
    if not isinstance(answers, dict) or not isinstance(answers.get(key), dict):
        return None, 0.0, {}
    answer = answers[key]
    probabilities = answer.get("probabilities", {})
    if not isinstance(probabilities, dict):
        return None, 0.0, {}
    try:
        probabilities = {k: score(v) for k, v in probabilities.items() if k in options}
        choice = answer.get("choice", answer.get("answer"))
        if choice is None and infer_choice and probabilities:
            choice = max(probabilities, key=probabilities.get)
        if not isinstance(choice, str) or choice not in options:
            return None, 0.0, probabilities
        confidence = score(answer.get("answer_confidence", answer.get("confidence", probabilities.get(choice, 0.0))))
    except (ValueError, TypeError):
        return None, 0.0, {}
    return choice, confidence, probabilities
