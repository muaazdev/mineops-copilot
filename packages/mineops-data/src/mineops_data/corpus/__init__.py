"""Bilingual SOP / manual corpus for Falcon Ridge Mining (SPEC §5).

Topic content is authored in YAML (``topics_*.yaml``, English and Arabic written separately);
this module renders one markdown file per (topic, language, version) with YAML frontmatter.
Rendering is pure and ordered, so the output is byte-identical on every run.

doc_id = ``<code>-<LANG>-R<version>``, e.g. ``LOTO-001-EN-R2``. Version N supersedes version
N-1 of the same language. An older version renders only for languages that author it.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml

Lang = Literal["en", "ar"]
LANGS: tuple[Lang, ...] = ("en", "ar")

HEADINGS: dict[Lang, dict[str, str]] = {
    "en": {
        "purpose": "Purpose",
        "scope": "Scope",
        "responsibilities": "Responsibilities",
        "ppe": "Personal Protective Equipment",
        "steps": "Procedure",
        "hazards": "Hazards and Controls",
        "records": "Records and Training",
        "references": "References",
    },
    "ar": {
        "purpose": "الغرض",
        "scope": "النطاق",
        "responsibilities": "المسؤوليات",
        "ppe": "معدات الوقاية الشخصية",
        "steps": "الإجراء",
        "hazards": "المخاطر وإجراءات التحكم",
        "records": "السجلات والتدريب",
        "references": "المراجع",
    },
}

# Shared boilerplate per document type. Real SOP libraries carry these sections too; they make
# documents long enough to chunk and give BM25 realistic common-term noise.
RESPONSIBILITIES: dict[Lang, dict[str, str]] = {
    "en": {
        "default": (
            "The site manager is accountable for implementing this document. Supervisors ensure "
            "that workers are trained and competent before they perform the tasks described, and "
            "they verify compliance during field inspections. Every worker follows this document, "
            "stops work when conditions are unsafe, and reports hazards and incidents to their "
            "supervisor without delay."
        ),
        "maintenance_manual": (
            "The maintenance superintendent owns this manual and keeps it aligned with the "
            "manufacturer's recommendations. Maintenance planners schedule the tasks in the "
            "maintenance system. Technicians perform the tasks, record measurements on the work "
            "order and report any condition outside the stated limits to their supervisor."
        ),
        "emergency_response": (
            "The emergency response coordinator maintains this plan and runs drills at least "
            "every six months. The control room coordinates the response and external services. "
            "Every person on site knows the alarm signals, the muster points and their role in "
            "an emergency."
        ),
    },
    "ar": {
        "default": (
            "مدير الموقع مسؤول عن تطبيق هذه الوثيقة. يتأكد المشرفون من تدريب العاملين وكفاءتهم "
            "قبل تنفيذ المهام الموضحة، ويتحققون من الالتزام خلال الجولات الميدانية. يلتزم كل عامل "
            "بهذه الوثيقة ويوقف العمل عندما تكون الظروف غير آمنة، ويبلغ المشرف عن المخاطر والحوادث "
            "دون تأخير."
        ),
        "maintenance_manual": (
            "مشرف الصيانة العام هو المالك لهذا الدليل ويحافظ على توافقه مع توصيات الشركة المصنعة. "
            "يجدول مخططو الصيانة المهام في نظام الصيانة. ينفذ الفنيون المهام ويسجلون القياسات في "
            "أمر العمل ويبلغون المشرف عن أي حالة خارج الحدود المحددة."
        ),
        "emergency_response": (
            "منسق الاستجابة للطوارئ مسؤول عن هذه الخطة وينفذ تمارين الطوارئ مرة كل ستة أشهر على "
            "الأقل. تنسق غرفة التحكم الاستجابة مع الجهات الخارجية. يعرف كل شخص في الموقع إشارات "
            "الإنذار ونقاط التجمع ودوره في حالات الطوارئ."
        ),
    },
}

RECORDS: dict[Lang, str] = {
    "en": (
        "Completed checklists, permits and work orders are retained in the site document system "
        "for at least five years. Workers complete training on this document before first use "
        "and refresher training every two years, or sooner when the document is revised."
    ),
    "ar": (
        "تحفظ قوائم الفحص والتصاريح وأوامر العمل المكتملة في نظام وثائق الموقع لمدة خمس سنوات على "
        "الأقل. يكمل العاملون التدريب على هذه الوثيقة قبل الاستخدام الأول، ويعاد التدريب كل سنتين "
        "أو قبل ذلك عند مراجعة الوثيقة."
    ),
}

FRONTMATTER_KEYS = (
    "doc_id",
    "title",
    "doc_type",
    "site",
    "asset_type",
    "lang",
    "version",
    "effective_date",
    "supersedes",
)


@dataclass(frozen=True)
class Document:
    doc_id: str
    code: str
    title: str
    doc_type: str
    site: str
    asset_type: str
    lang: Lang
    version: int
    effective_date: date
    supersedes: str | None
    body: dict[str, Any]

    def frontmatter(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in FRONTMATTER_KEYS}


def doc_id(code: str, lang: Lang, version: int) -> str:
    return f"{code}-{lang.upper()}-R{version}"


def load_topics() -> list[dict[str, Any]]:
    pkg = resources.files(__package__)
    topics: list[dict[str, Any]] = []
    for name in sorted(p.name for p in pkg.iterdir() if p.name.startswith("topics_")):
        topics.extend(yaml.safe_load(pkg.joinpath(name).read_text(encoding="utf-8")))
    codes = [t["code"] for t in topics]
    if len(codes) != len(set(codes)):
        raise ValueError("duplicate topic codes in corpus YAML")
    return topics


def iter_documents(topics: list[dict[str, Any]] | None = None) -> Iterator[Document]:
    for topic in topics if topics is not None else load_topics():
        versions = topic.get("versions") or [
            {"version": 1, "effective_date": topic["effective_date"]}
        ]
        latest = max(v["version"] for v in versions)
        for lang in LANGS:
            if lang not in topic:
                continue
            prev: str | None = None
            for v in sorted(versions, key=lambda v: v["version"]):
                override = v.get(lang)
                if override is None and v["version"] != latest:
                    continue  # this language does not author that older revision
                body = {**topic[lang], **(override or {})}
                did = doc_id(topic["code"], lang, v["version"])
                yield Document(
                    doc_id=did,
                    code=topic["code"],
                    title=body["title"],
                    doc_type=topic["doc_type"],
                    site=topic["site"],
                    asset_type=topic["asset_type"],
                    lang=lang,
                    version=v["version"],
                    effective_date=v["effective_date"],
                    supersedes=prev,
                    body=body,
                )
                prev = did


def render(doc: Document) -> str:
    h = HEADINGS[doc.lang]
    resp = RESPONSIBILITIES[doc.lang]
    fm_lines = ["---"]
    for key, value in doc.frontmatter().items():
        if value is None:
            rendered = "null"
        elif isinstance(value, date):
            rendered = value.isoformat()
        elif isinstance(value, int):
            rendered = str(value)
        else:
            rendered = yaml.safe_dump(value, allow_unicode=True, default_style='"').strip()
        fm_lines.append(f"{key}: {rendered}")
    fm_lines.append("---")
    b = doc.body
    sections = [
        ("purpose", b["purpose"].strip()),
        ("scope", b["scope"].strip()),
        ("responsibilities", resp.get(doc.doc_type, resp["default"])),
        ("ppe", "\n".join(f"- {item}" for item in b["ppe"])),
        ("steps", "\n".join(f"{i}. {s}" for i, s in enumerate(b["steps"], start=1))),
        ("hazards", "\n".join(f"- {item}" for item in b["hazards"])),
        ("records", RECORDS[doc.lang]),
        ("references", "\n".join(f"- {r}" for r in b.get("references", []))),
    ]
    out = [*fm_lines, "", f"# {doc.title}", ""]
    for n, (key, text) in enumerate(sections, start=1):
        if text:
            out += [f"## {n}. {h[key]}", "", text, ""]
    return "\n".join(out).rstrip("\n") + "\n"


def write_corpus(out: Path) -> list[Document]:
    """Render every document into ``out`` (stale ``*.md`` files are removed first)."""
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.md"):
        stale.unlink()
    docs = list(iter_documents())
    for doc in docs:
        (out / f"{doc.doc_id}.md").write_text(render(doc), encoding="utf-8")
    return docs
