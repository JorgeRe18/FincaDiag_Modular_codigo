import zipfile
import shutil
import re
from pathlib import Path
from io import BytesIO

dir_path = Path('vali_presencial_SG')

def fix_docx(path: Path) -> dict:
    backup = path.with_suffix('.docx.backup')
    tmp = path.with_suffix('.docx.tmp')

    # Backup if not exists
    if not backup.exists():
        shutil.copy2(path, backup)

    with zipfile.ZipFile(path, 'r') as zin:
        xml_text = zin.read('word/document.xml').decode('utf-8', errors='ignore')

    count_before = xml_text.lower().count('observación')
    count_missing_colon = len(re.findall(r'observacion(?!:)', xml_text, re.IGNORECASE))

    if count_before == 0 and count_missing_colon == 0:
        return {
            'file': path.name,
            'changed': False,
            'reason': 'sin_problemas',
            'tilde_count': 0,
            'missing_colon': 0,
        }

    # Apply fix
    xml_fixed = re.sub(r'observaci[oó]n(?!:)', 'observacion:', xml_text, flags=re.IGNORECASE)

    # Verify
    count_after = xml_fixed.lower().count('observación')
    missing_after = len(re.findall(r'observacion(?!:)', xml_fixed, re.IGNORECASE))

    # Write new ZIP
    data = BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as zout:
        with zipfile.ZipFile(path, 'r') as zin:
            for item in zin.infolist():
                content = zin.read(item.filename)
                if item.filename == 'word/document.xml':
                    content = xml_fixed.encode('utf-8')
                zout.writestr(item, content)

    with tmp.open('wb') as f:
        f.write(data.getvalue())

    shutil.move(str(tmp), str(path))

    return {
        'file': path.name,
        'changed': True,
        'tilde_before': count_before,
        'missing_colon_before': count_missing_colon,
        'tilde_after': count_after,
        'missing_colon_after': missing_after,
    }

# Process all docx files
results = []
for docx in sorted(dir_path.glob('validacion_visita_*.docx')):
    # Skip backups
    if docx.name.endswith('.backup'):
        continue
    results.append(fix_docx(docx))

print('=== RESULTADOS ===\n')
changed = 0
unchanged = 0
for r in results:
    if r['changed']:
        changed += 1
        print(f"CORREGIDO: {r['file']}")
        print(f"  observación (tilde): {r['tilde_before']} -> {r['tilde_after']}")
        print(f"  observacion sin ':': {r['missing_colon_before']} -> {r['missing_colon_after']}")
        print()
    else:
        unchanged += 1
        print(f"OK: {r['file']} ({r['reason']})")

print(f'\nTotal: {len(results)} archivos')
print(f'Corregidos: {changed}')
print(f'Sin cambios: {unchanged}')
