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
        if self.url:
            base = self.url.strip().lower()
            base = re.sub(r"([?&])(utm[a-z_]*|source|src|ref|lang|locale|codes)=[^&#]*", r"\1", base)
            base = re.sub(r"[?&]+$", "", base.replace("?&", "?")).rstrip("/")
            if "#card=" in base:
                base = base.split("#")[0] + "|card|" + self.title.strip().lower()
            elif "#" in base and not re.search(r"#.*job", base):
                base = base.split("#")[0]
        else:
            base = f"{self.company}|{self.title}|{self.location}".lower()
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    def to_dict(self):
        d = asdict(self)
        d["key"] = self.key
        return d
