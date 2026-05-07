import csv
import json
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from src.config import AppConfig
from src.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = (
    PROJECT_ROOT / "data" / "compliance" / "public_sector_entities.csv"
)


@dataclass(frozen=True)
class ComplianceEntity:
    entity_name: str
    aliases: tuple[str, ...]
    country: str = "global"
    entity_type: str = "keyword"
    risk_level: str = "HIGH"
    source: str = "curated"
    source_date: str = ""
    notes: str = ""

    @property
    def terms(self) -> tuple[str, ...]:
        return (self.entity_name, *self.aliases)


@dataclass(frozen=True)
class ComplianceMatch:
    entity: ComplianceEntity
    matched_term: str

    @property
    def evidence(self) -> str:
        details = [
            f"entity: {self.entity.entity_name}",
            f"matched term: {self.matched_term}",
            f"type: {self.entity.entity_type}",
            f"country: {self.entity.country}",
            f"source: {self.entity.source}",
        ]
        if self.entity.source_date:
            details.append(f"source date: {self.entity.source_date}")
        return "; ".join(details)


@dataclass(frozen=True)
class ComplianceCatalog:
    entities: tuple[ComplianceEntity, ...]
    source_name: str

    def find_public_sector_matches(self, text: str) -> list[ComplianceMatch]:
        matches = []
        for entity in self.entities:
            for term in entity.terms:
                if term and term_matches(text, term):
                    matches.append(ComplianceMatch(entity=entity, matched_term=term))
                    break
        return matches


def normalized_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def term_matches(text: str, term: str) -> bool:
    normalized_text = f" {normalized_words(text)} "
    normalized_term = normalized_words(term)
    if not normalized_term:
        return False
    return f" {normalized_term} " in normalized_text


def split_aliases(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    aliases = [
        alias.strip() for alias in re.split(r"[|;]", value) if alias and alias.strip()
    ]
    return tuple(dict.fromkeys(aliases))


def entity_from_mapping(row: dict[str, Any]) -> ComplianceEntity | None:
    name = str(row.get("entity_name") or row.get("name") or "").strip()
    aliases = split_aliases(str(row.get("aliases") or ""))
    if not name and not aliases:
        return None
    risk_level = str(row.get("risk_level") or row.get("severity") or "HIGH").upper()
    if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
        risk_level = "HIGH"
    return ComplianceEntity(
        entity_name=name or aliases[0],
        aliases=aliases,
        country=str(row.get("country") or "global").strip() or "global",
        entity_type=str(row.get("type") or row.get("entity_type") or "keyword").strip()
        or "keyword",
        risk_level=risk_level,
        source=str(row.get("source") or "curated").strip() or "curated",
        source_date=str(row.get("source_date") or row.get("date") or "").strip(),
        notes=str(row.get("notes") or "").strip(),
    )


def parse_compliance_entities(text: str, source_name: str) -> ComplianceCatalog:
    stripped = text.lstrip()
    rows: list[dict[str, Any]]
    if stripped.startswith("["):
        loaded = json.loads(text)
        if not isinstance(loaded, list):
            raise ValueError("Compliance JSON must be a list of entity objects.")
        rows = [item for item in loaded if isinstance(item, dict)]
    else:
        rows = list(csv.DictReader(StringIO(text)))
    entities = tuple(
        entity for row in rows if (entity := entity_from_mapping(row)) is not None
    )
    if not entities:
        raise ValueError(f"No compliance entities were found in {source_name}.")
    return ComplianceCatalog(entities=entities, source_name=source_name)


def default_catalog_text() -> str:
    return DEFAULT_CATALOG_PATH.read_text(encoding="utf-8")


def load_local_compliance_catalog() -> ComplianceCatalog:
    return parse_compliance_entities(
        default_catalog_text(),
        source_name=str(DEFAULT_CATALOG_PATH.relative_to(PROJECT_ROOT)),
    )


def load_compliance_catalog(
    config: AppConfig,
    object_storage=None,
) -> ComplianceCatalog:
    object_name = getattr(
        config,
        "compliance_entities_object_name",
        "compliance/public_sector_entities.csv",
    )
    if object_storage and object_name:
        try:
            return parse_compliance_entities(
                object_storage.get_object_text(object_name),
                source_name=f"Object Storage: {object_name}",
            )
        except Exception as exc:
            logger.warning(
                "Could not load compliance entity catalog from Object Storage object %s: %s",
                object_name,
                exc,
            )
            try:
                object_storage.put_text(object_name, default_catalog_text())
                return parse_compliance_entities(
                    object_storage.get_object_text(object_name),
                    source_name=f"Object Storage: {object_name}",
                )
            except Exception as seed_exc:
                logger.warning(
                    "Could not seed compliance entity catalog to Object Storage object %s: %s",
                    object_name,
                    seed_exc,
                )
    return load_local_compliance_catalog()
