"""Preflight the JSON sheets and generate the Cemu patch and runtime definitions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def preflight():
    sheets = {p.stem: json.loads(p.read_text()) for p in (ROOT / 'sheets').glob('*.json')}
    errors = []
    for name, tables in sheets.items():
        for table, rows in tables.items():
            columns = set().union(*(r.keys() for r in rows))
            ids = set()
            for row in rows:
                if row.get('id') in ids:
                    errors.append(f'{name}.{table}: duplicate {row.get("id")}')
                ids.add(row.get('id'))
                for column in columns:
                    if column not in row or row[column] is None or row[column] == '':
                        errors.append(f'{name}.{table}.{row.get("id")}.{column}: unfilled')
    design, hooks = sheets['design'], sheets['hooks']
    systems = {r['id'] for r in design['systems']}
    targets = {r['id'] for r in hooks['target']}
    for row in design['controls']:
        if row['system'] not in systems:
            errors.append(f'control {row["id"]}: unresolved system')
    for row in design['systems']:
        if row['target'] not in targets:
            errors.append(f'system {row["id"]}: unresolved target')
    blocks = {r['id'] for r in design['blocks']}
    for row in design.get('textures',[]):
        if row['block'] not in blocks:
            errors.append(f'texture {row["id"]}: unresolved block')
    for row in hooks['hooks']:
        if str(row['address']).lower() not in row['evidence'].lower():
            errors.append(f'hook {row["id"]}: address/evidence mismatch')
    if errors:
        raise SystemExit('PREBUILD FAILED\n' + '\n'.join(errors))
    print('Preflight: every cell filled; all references resolve; hook addresses match evidence.')
    return design, hooks


def build():
    design, hooks = preflight()
    generated = ROOT / 'generated'
    generated.mkdir(exist_ok=True)
    definitions = ['# Generated from sheets; edit the sheets first.', 'from types import SimpleNamespace']
    for table, rows in {**design, **hooks}.items():
        definitions.append(f'{table.upper()} = {{')
        for row in rows:
            definitions.append(f'    {row["id"]!r}: SimpleNamespace(**{row!r}),')
        definitions.append('}')
    (generated / 'design.py').write_text('\n'.join(definitions) + '\n')
    pack = generated / 'HyruleBlocks'
    pack.mkdir(exist_ok=True)
    target = hooks['target'][0]
    (pack / 'rules.txt').write_text('[Definition]\n'
        f'titleIds = {target["title"]}\n'
        'name = Hyrule Blocks (experimental)\n'
        'path = "The Legend of Zelda: Breath of the Wild/Mods/Hyrule Blocks"\n'
        'description = Experimental block placement bridge. Requires the companion and update 208.\n'
        'version = 7\n')
    source = (ROOT / 'src' / 'bridge.asm').read_text()
    replacements = {row['id'].replace('-', '_').upper(): row['address'] for row in hooks['hooks']}
    replacements['MODULE'] = target['module']
    replacements['PLAYER_SINGLETON'] = next(row['offset'] for row in hooks['fields'] if row['id']=='player-singleton')
    replacements['MAILBOX_DATA'] = '.byte ' + ', '.join(str(b) for b in b'HYRULEBLOCKS_v03') + '\n' + '\n'.join(['.double 0'] * 78)
    for key, value in replacements.items():
        source = source.replace('{{' + key + '}}', str(value))
    if '{{' in source:
        raise SystemExit('Unresolved assembly substitution')
    (pack / 'patch_bridge.asm').write_text(source)
    print(f'Generated {pack}; runtime testing remains required.')


if __name__ == '__main__':
    build()
