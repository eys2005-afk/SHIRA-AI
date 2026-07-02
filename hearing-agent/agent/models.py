"""מודל של דיון אחד ביומן, כפי שהוא זורם בין שירה -> Verbit -> הדשבורד."""

import hashlib
from dataclasses import dataclass, field, asdict

# מחזור החיים של דיון:
#   pending    - נקרא מהיומן, טרם נקבע ב-Verbit
#   scheduled  - נקבע ב-Verbit, מוכן להפעלה
#   recording  - ההקלטה רצה כרגע
#   done       - ההקלטה הסתיימה
#   error      - קביעה/הפעלה נכשלה (הפרטים בשדה error)
STATUSES = ("pending", "scheduled", "recording", "done", "error")


@dataclass
class Hearing:
    date: str                       # YYYY-MM-DD
    time: str                       # HH:MM כפי שמופיע ביומן
    case_number: str
    case_title: str = ""
    parties: list = field(default_factory=list)
    status: str = "pending"
    verbit_session_id: str = ""
    verbit_url: str = ""            # קישור ישיר לדיון ב-Verbit
    error: str = ""

    @property
    def id(self) -> str:
        raw = f"{self.date}|{self.time}|{self.case_number}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Hearing":
        d = {k: v for k, v in d.items() if k != "id"}
        return cls(**d)
