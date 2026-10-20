#!/usr/bin/env python3
"""Generate a local CSV fixture using the canonical client-ingestion contract."""

import argparse
import csv
from pathlib import Path


CANONICAL_COLUMNS = (
    "id_cliente",
    "tier",
    "frequencia",
    "recencia_dias",
    "gasto_total",
    "incidentes",
)
TIERS = ("Básico", "Topázio", "Safira", "Diamante")


def generate_rows(count: int) -> list[dict[str, str | int | float]]:
    if count < 1:
        raise ValueError("count must be at least 1")

    rows = []
    for index in range(count):
        rows.append(
            {
                "id_cliente": f"synthetic-{index + 1:04d}",
                "tier": TIERS[index % len(TIERS)],
                "frequencia": (index % 20) + 1,
                "recencia_dias": (index * 7) % 121,
                "gasto_total": round(250.0 + index * 125.5, 2),
                "incidentes": index % 4,
            }
        )
    return rows


def write_csv(output_path: Path, count: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(generate_rows(count))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination CSV path (for example /tmp/synthetic_clients.csv).",
    )
    parser.add_argument("--rows", type=int, default=20, help="Number of rows to generate.")
    args = parser.parse_args()
    write_csv(args.output, args.rows)
    print(f"Generated {args.rows} canonical synthetic client rows: {args.output}")


if __name__ == "__main__":
    main()
