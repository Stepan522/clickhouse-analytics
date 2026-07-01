import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from models import LeadRequest


def test_phone_is_normalized() -> None:
    lead = LeadRequest(
        name="Иван",
        phone="8 (999) 123-45-67",
        email="ivan@example.com",
        service="Автоматизация отчетности",
    )
    assert lead.phone == "+79991234567"
