from __future__ import annotations

from datetime import datetime
from typing import Iterator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Company


@pytest.fixture(name="session")
def session_fixture() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        company = Company(name="Test Co", timezone="Asia/Kolkata")
        session.add(company)
        session.commit()
        session.refresh(company)
        yield session


@pytest.fixture(name="company")
def company_fixture(session: Session) -> Company:
    company = session.exec(select(Company)).first()
    assert company is not None
    return company


@pytest.fixture(name="now")
def now_fixture() -> datetime:
    return datetime(2024, 8, 14, 8, 30)
