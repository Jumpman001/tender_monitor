"""
Dataclass модель тендера.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Tender:
    """Представление одного тендера."""

    hash: str
    source: str
    title: str
    url: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    donor: Optional[str] = None
    contractor: Optional[str] = None
    budget: Optional[str] = None
    pipe_diameter: Optional[str] = None
    tender_deadline: Optional[str] = None
    contract_completion: Optional[str] = None
    status: str = "Unknown"
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    region: Optional[str] = None
    ai_card: Optional[str] = None
    first_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notified: int = 0
    id: Optional[int] = None

    # Дополнительные поля из AI (не хранятся в БД напрямую, используются для карточки)
    pipe_type: Optional[str] = None
    pipe_length_km: Optional[str] = None
    urgency: str = "LOW"
    summary_ru: Optional[str] = None

    def to_db_tuple(self) -> tuple:
        """Возвращает кортеж для вставки в БД (без id)."""
        return (
            self.hash,
            self.source,
            self.title,
            self.description,
            self.project_id,
            self.donor,
            self.contractor,
            self.budget,
            self.pipe_diameter,
            self.tender_deadline,
            self.contract_completion,
            self.status,
            self.contact_email,
            self.contact_phone,
            self.contact_name,
            self.url,
            self.region,
            self.ai_card,
            self.first_seen,
            self.last_updated,
            self.notified,
        )

    @classmethod
    def from_db_row(cls, row: dict) -> "Tender":
        """Создаёт Tender из строки БД (dict)."""
        return cls(
            id=row.get("id"),
            hash=row["hash"],
            source=row["source"],
            title=row["title"],
            description=row.get("description"),
            project_id=row.get("project_id"),
            donor=row.get("donor"),
            contractor=row.get("contractor"),
            budget=row.get("budget"),
            pipe_diameter=row.get("pipe_diameter"),
            tender_deadline=row.get("tender_deadline"),
            contract_completion=row.get("contract_completion"),
            status=row.get("status", "Unknown"),
            contact_email=row.get("contact_email"),
            contact_phone=row.get("contact_phone"),
            contact_name=row.get("contact_name"),
            url=row["url"],
            region=row.get("region"),
            ai_card=row.get("ai_card"),
            first_seen=row.get("first_seen", ""),
            last_updated=row.get("last_updated", ""),
            notified=row.get("notified", 0),
        )


@dataclass
class ScanLog:
    """Запись лога сканирования."""

    scanned_at: str
    source: str
    found_total: int = 0
    new_tenders: int = 0
    errors: Optional[str] = None
    id: Optional[int] = None
