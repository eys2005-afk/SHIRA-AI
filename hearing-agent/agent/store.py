"""אחסון מקומי פשוט: קובץ JSON אחד ליום, בתיקיית data/.

זה כל "מסד הנתונים" של הסוכן - קריא בעין, קל לגבות, ואין מה להתקין.
"""

import json
from datetime import date
from pathlib import Path

from .models import Hearing


class DayStore:
    def __init__(self, data_dir: str, day: str | None = None):
        self.day = day or date.today().isoformat()
        self.path = Path(data_dir) / f"hearings-{self.day}.json"

    def load(self) -> list[Hearing]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [Hearing.from_dict(d) for d in json.load(f)]

    def save(self, hearings: list[Hearing]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([h.to_dict() for h in hearings], f, ensure_ascii=False, indent=2)

    def merge(self, fresh: list[Hearing]) -> list[Hearing]:
        """ממזג דיונים שנקראו עכשיו מהיומן עם המצב השמור.

        דיון שכבר נקבע ב-Verbit שומר על הסטטוס ופרטי ה-Verbit שלו גם אם
        היומן נקרא שוב (למשל בלחיצת רענון בדשבורד); דיונים חדשים מתווספים.
        """
        existing = {h.id: h for h in self.load()}
        merged = []
        for h in fresh:
            if h.id in existing:
                merged.append(existing.pop(h.id))
            else:
                merged.append(h)
        # דיונים שנשמרו קודם ולא הופיעו עכשיו ביומן - נשארים (ליתר ביטחון)
        merged.extend(existing.values())
        merged.sort(key=lambda h: h.time)
        self.save(merged)
        return merged

    def update(self, hearing_id: str, **fields) -> Hearing | None:
        hearings = self.load()
        target = None
        for h in hearings:
            if h.id == hearing_id:
                for k, v in fields.items():
                    setattr(h, k, v)
                target = h
        self.save(hearings)
        return target
