"""Readability scores from textstat."""

from pathlib import Path

import nltk
import textstat

from vc_evals.layer2.result import Result
from vc_evals.layer2.text import Prepared

# textstat reads the CMU dictionary from nltk's path; this puts the copy in the repo first.
nltk.data.path.insert(0, str(Path(__file__).parent / "nltk_data"))

NAME = "readability"
DESCRIPTION = "Flesch Reading Ease (higher is easier) and Flesch-Kincaid grade (US school grade)."


def measure(prepared: Prepared) -> Result:
    sentences = prepared.sentences
    if not sentences:
        return Result({"Flesch reading ease": "-", "Flesch-Kincaid grade": "-"})
    text = " ".join(sentences)
    try:
        ease, grade = textstat.flesch_reading_ease(text), textstat.flesch_kincaid_grade(text)
    except LookupError:  # the CMU dictionary was not found on nltk's path
        return Result(
            {"Flesch reading ease": "n/a", "Flesch-Kincaid grade": "n/a"},
            ["textstat could not load the CMU pronouncing dictionary."],
        )
    return Result({"Flesch reading ease": round(ease, 1), "Flesch-Kincaid grade": round(grade, 1)})
