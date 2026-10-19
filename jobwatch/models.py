from dataclasses import dataclass, field, asdict
import hashlib
import re


@dataclass
class Job:
    company: str
    title: str
    url: str
    location: str = ""
    posted: str = ""          # free text / ISO date if the source gives it
    source: str = ""          # adapter name
    description: str = ""     # optional snippet, used only for "years of experience" filtering
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Stable id for de-duplication. Prefer the URL; fall back to company+title+location."""
        base = self.url.strip().lower() if self.url else f"{self.company}|{self.title}|{self.location}".lower()
        base = re.sub(r"[?#].*$", "", base) if self.url else base
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    def to_dict(self):
        d = asdict(self)
        d["key"] = self.key
        return d
