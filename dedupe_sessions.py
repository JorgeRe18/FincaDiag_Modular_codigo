"""
Deduplica sesiones de captura en data/processed/visits/.

Politica: para cada (visita, timestamp), conserva la carpeta con el mtime
mas reciente. Las demas se mueven a data/processed/_duplicates/<visit>/.

Uso:
  python dedupe_sessions.py           # dry-run (solo muestra)
  python dedupe_sessions.py --apply   # ejecuta el movimiento
"""
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
PROCESSED = BASE / 'data' / 'processed' / 'visits'
DUP_TRASH = BASE / 'data' / 'processed' / '_duplicates'

APPLY = '--apply' in sys.argv


def find_duplicates():
    """Devuelve dict: (visit, timestamp) -> lista de paths ordenados por mtime DESC."""
    groups = {}
    for v in sorted(PROCESSED.iterdir()):
        if not v.is_dir() or not v.name.startswith('Visita_'):
            continue
        ses = v / 'sesiones'
        if not ses.exists():
            continue
        for s in ses.iterdir():
            if not s.is_dir() or 'Captura_' not in s.name:
                continue
            m = re.search(r'(\d{8}_\d{6})$', s.name)
            if not m:
                continue
            ts = m.group(1)
            groups.setdefault((v.name, ts), []).append(s)

    dups = {}
    for key, paths in groups.items():
        if len(paths) > 1:
            # Ordenar por mtime DESC (mas reciente primero)
            paths_sorted = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
            dups[key] = paths_sorted
    return dups


def main():
    dups = find_duplicates()
    if not dups:
        print('No hay duplicados.')
        return

    total_keep = len(dups)
    total_move = sum(len(paths) - 1 for paths in dups.values())

    print(f"Encontrados {total_keep} grupos con duplicados, {total_move} carpetas a mover.\n")

    mode = 'EJECUTANDO' if APPLY else 'DRY-RUN (no se mueve nada)'
    print(f'=== {mode} ===\n')

    moved = 0
    for (visit, ts), paths in sorted(dups.items()):
        keep = paths[0]
        keep_mtime = datetime.fromtimestamp(keep.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        print(f"[{visit}] ts={ts}")
        print(f"  KEEP   ({keep_mtime}): {keep.name}")
        for dup in paths[1:]:
            dup_mtime = datetime.fromtimestamp(dup.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            print(f"  MOVE   ({dup_mtime}): {dup.name}")
            if APPLY:
                dest_dir = DUP_TRASH / visit
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / dup.name
                if dest.exists():
                    # Append timestamp si ya existe
                    dest = dest_dir / f"{dup.name}__moved_{int(dup.stat().st_mtime)}"
                shutil.move(str(dup), str(dest))
                moved += 1

    print()
    if APPLY:
        print(f'Movidas {moved} carpetas a {DUP_TRASH}')
    else:
        print(f'Para ejecutar realmente: python dedupe_sessions.py --apply')


if __name__ == '__main__':
    main()
