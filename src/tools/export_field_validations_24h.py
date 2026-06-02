import csv
from collections import defaultdict
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincadiag.analysis import field_validation
from fincadiag.config import DATA_FIELD_VALIDATION_DIR, PROJECT_ROOT


CSV_PATH = DATA_FIELD_VALIDATION_DIR / "validaciones_presenciales_24h.csv"
TXT_PATH = PROJECT_ROOT / "docs" / "validaciones_presenciales_24h.txt"

FIELDNAMES = [
    "visit_date",
    "block",
    "milking_start",
    "milking_end",
    "cow_number",
    "tag_allflex",
    "tag_lookup_status",
    "entry_time",
    "id_time",
    "exit_time",
    "id_read_status",
    "flow_visible_status",
    "observation",
    "source_doc",
]


def main() -> None:
    rows = field_validation._load_validation_rows()
    rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("visit_date", "")),
            str(row.get("block", "")),
            str(row.get("entry_time", "")),
            str(row.get("cow_number", "")),
        ),
    )

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    TXT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in FIELDNAMES})

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row.get("visit_date", ""), row.get("block", ""))].append(row)

    lines = [
        "VALIDACIONES PRESENCIALES NORMALIZADAS A 24H",
        "Fuente: DOCX/CSV locales procesados por FincaDiag.",
        "Nota: este archivo es canónico para revisión humana; el motor ya normaliza internamente estas horas.",
        "",
    ]
    for (visit_date, block), group in sorted(grouped.items()):
        lines.append(f"## {visit_date} {block}")
        if group:
            lines.append(f"Ventana de ordeño: {group[0].get('milking_start', '')} - {group[0].get('milking_end', '')}")
            lines.append(f"Vacas registradas: {len({str(row.get('cow_number', '')).strip() for row in group if str(row.get('cow_number', '')).strip()})}")
        for row in group:
            lines.append(
                "Vaca {cow} | entrada {entry} | tag {tag_time} | salida {exit} | "
                "rfid {rfid} | flujo {flow} | doc {doc}".format(
                    cow=row.get("cow_number", ""),
                    entry=row.get("entry_time", ""),
                    tag_time=row.get("id_time", ""),
                    exit=row.get("exit_time", ""),
                    rfid=row.get("id_read_status", ""),
                    flow=row.get("flow_visible_status", ""),
                    doc=row.get("source_doc", ""),
                )
            )
        lines.append("")

    TXT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] CSV 24H: {CSV_PATH}")
    print(f"[OK] TXT 24H: {TXT_PATH}")
    print(f"[OK] Registros exportados: {len(rows)}")
    print(f"[OK] Bloques: {len(grouped)}")


if __name__ == "__main__":
    main()
