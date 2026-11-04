"""Configuração lida de variáveis de ambiente (.env opcional na raiz do repositório)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)  # fora do repr: não vaza se o objeto for logado
    seed: int

    def url(self) -> URL:
        """URL do SQLAlchemy. O objeto URL escapa a senha corretamente."""
        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            query={"charset": "utf8mb4"},
        )


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variável de ambiente ausente: {name}. Copie .env.example para .env e preencha.")
    return value


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        database=_required("MYSQL_DATABASE"),
        user=_required("MYSQL_USER"),
        password=_required("MYSQL_PASSWORD"),
        seed=int(os.environ.get("SEED", "42")),
    )
