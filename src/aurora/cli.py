"""Linha de comando: init-db, seed, report e all."""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from aurora.analysis.pipeline import run_analysis
from aurora.charts import render_all
from aurora.config import FIGURES_DIR, REPORTS_DIR, Settings, load_settings
from aurora.db import apply_schema, make_engine
from aurora.generator import GeneratorConfig, generate
from aurora.loader import load
from aurora.report import write_report
from aurora.safety import confirm_destructive

logger = logging.getLogger("aurora")


def cmd_init_db(settings: Settings) -> None:
    apply_schema(make_engine(settings))


def cmd_seed(settings: Settings) -> None:
    data = generate(GeneratorConfig(seed=settings.seed))
    counts = load(make_engine(settings), data)
    logger.info("Carga concluída: %s", ", ".join(f"{t}={n}" for t, n in counts.items()))


def cmd_report(settings: Settings) -> None:
    results = run_analysis(make_engine(settings))
    render_all(results, FIGURES_DIR)
    path = write_report(results, REPORTS_DIR / "report.md")
    logger.info("Relatório gerado: %s", path)


def cmd_all(settings: Settings) -> None:
    cmd_init_db(settings)
    cmd_seed(settings)
    cmd_report(settings)


COMMANDS = {"init-db": cmd_init_db, "seed": cmd_seed, "report": cmd_report, "all": cmd_all}
DESTRUCTIVE = {"init-db", "seed", "all"}  # apagam tabelas ou dados: exigem confirmação


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aurora", description="Pipeline de análise da Loja Aurora (dados fictícios)")
    parser.add_argument("command", choices=COMMANDS, help="init-db: cria o esquema | seed: gera e carrega dados | "
                                                           "report: gráficos e relatório | all: os três em sequência")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs detalhados")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="não pedir confirmação antes de apagar dados (init-db, seed, all)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    try:
        settings = load_settings()
        if args.command in DESTRUCTIVE and not confirm_destructive(settings, args.yes):
            logger.error("Operação cancelada: nada foi apagado. Confirme digitando o nome do banco "
                         "ou use --yes em execuções sem terminal.")
            return 1
        COMMANDS[args.command](settings)
    except (RuntimeError, SQLAlchemyError) as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
