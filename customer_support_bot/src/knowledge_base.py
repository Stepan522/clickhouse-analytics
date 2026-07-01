from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


class KnowledgeBase:
    """Простая база знаний для FAQ-бота.

    В реальном проекте CSV можно заменить на Notion, Google Sheets,
    базу данных, CMS или векторный поиск.
    """

    def __init__(self, faq_path: str | Path) -> None:
        self.faq_path = Path(faq_path)
        self.faq = pd.read_csv(self.faq_path)

    @staticmethod
    def normalize(text: str) -> set[str]:
        text = text.lower().replace("ё", "е")
        tokens = re.findall(r"[a-zа-я0-9]+", text)
        stop_words = {"как", "где", "что", "когда", "можно", "нужно", "по", "на", "и", "в"}
        return {token for token in tokens if token not in stop_words}

    def find_answer(self, question: str) -> dict:
        """Ищет лучший ответ по пересечению слов с вопросом и FAQ."""
        question_tokens = self.normalize(question)

        best_score = 0
        best_row = None

        for _, row in self.faq.iterrows():
            faq_tokens = self.normalize(row["question"] + " " + row["answer"] + " " + row["category"])
            score = len(question_tokens & faq_tokens)

            if score > best_score:
                best_score = score
                best_row = row

        if best_row is None or best_score == 0:
            return {
                "found": False,
                "intent": "unknown",
                "answer": "Я не нашел точный ответ. Передаю вопрос оператору.",
                "need_operator": True,
            }

        need_operator = best_score < 2
        return {
            "found": True,
            "intent": best_row["intent"],
            "category": best_row["category"],
            "answer": best_row["answer"],
            "need_operator": need_operator,
            "score": best_score,
        }
