import copy
import argparse
import hashlib
import urllib.request
import csv
import io
import json
import struct
from pathlib import Path
import UnityPy
import lz4.block
from UnityPy.helpers import CompressionHelper

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--game-dir', type=Path, required=True)
parser.add_argument('--out-dir', type=Path, required=True)
args = parser.parse_args()
game = args.game_dir.resolve()
output = args.out_dir.resolve()
if game == output or game in output.parents or output in game.parents:
    raise ValueError('Source game and output directory must be separate')
metadata = json.loads((root / 'sources.json').read_text(encoding='utf-8'))
for relative, expected in metadata['files'].items():
    with (game / relative).open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('Unsupported source file: ' + relative)
font_root = root / 'fonts'
font_root.mkdir(exist_ok=True)
for name, info in metadata['fonts'].items():
    target = font_root / name
    if not target.exists():
        urllib.request.urlretrieve(info['url'], target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != info['sha256']:
        raise ValueError('Font checksum mismatch: ' + name)
CompressionHelper.COMPRESSION_MAP[2] = lambda data: lz4.block.compress(data, mode='fast', store_size=False)
data_name = 'How Much for the Body in the Freezer_Data'
original = next((game / data_name).glob('StreamingAssets/aa/StandaloneWindows64/default*.bundle'))
source = output / original.relative_to(game)
source.parent.mkdir(parents=True, exist_ok=True)
env = UnityPy.load(str(original))
objects = list(env.objects)
font_template = next(o for o in objects if o.type.name == 'Font' and o.read().m_Name == 'GenWanMin-R')
font_ids = {}
template_raw = font_template.get_raw_data()
template_font = bytes(font_template.read().m_FontData)
font_offset = template_raw.find(template_font)
assert font_offset >= 4 and struct.unpack_from('<I', template_raw, font_offset - 4)[0] == len(template_font)
for offset, weight in enumerate(['M', 'L']):
    duplicate = copy.copy(font_template)
    duplicate.path_id = 9100000000000000000 + offset
    new_font = (font_root / ('GenWanMin-' + weight + '.ttc')).read_bytes()
    old_end = font_offset + len(template_font)
    old_end += -old_end % 4
    replacement = struct.pack('<I', len(new_font)) + new_font
    replacement += b'\0' * (-(font_offset - 4 + len(replacement)) % 4)
    duplicate.assets_file.objects[duplicate.path_id] = duplicate
    duplicate.set_raw_data(template_raw[:font_offset - 4] + replacement + template_raw[old_end:])
    print('Added font source', weight, flush=True)
    font_ids[weight] = duplicate.path_id

stats = {}
font_assets = {}
for obj in objects:
    if obj.type.name == 'MonoBehaviour':
        tree = obj.read_typetree()
        if 'm_CharacterTable' in tree:
            font_assets[tree['m_Name']] = (obj, tree)
dynamic_obj, dynamic_tree = font_assets['GenWanMin-R SDF']
objects_by_id = {o.path_id: o for o in objects}
def remap(value, references):
    if isinstance(value, dict):
        if value.get('m_FileID') == 0 and value.get('m_PathID') in references:
            return {'m_FileID': 0, 'm_PathID': references[value['m_PathID']]}
        return {k: remap(v, references) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [remap(v, references) for v in value]
        return tuple(items) if isinstance(value, tuple) else items
    return value
for offset, weight in enumerate(['M', 'L']):
    original_obj, original_tree = font_assets['GenWanMin-' + weight + ' SDF']
    source_ids = [dynamic_obj.path_id, dynamic_tree['m_Material']['m_PathID'], dynamic_tree['m_AtlasTextures'][0]['m_PathID']]
    references = {old: 9100000000000000100 + offset * 10 + i for i, old in enumerate(source_ids)}
    for old in source_ids:
        template = objects_by_id[old]
        new = copy.copy(template)
        new.path_id = references[old]
        new.assets_file.objects[new.path_id] = new
        tree = remap(template.read_typetree(), references)
        tree['m_Name'] = 'GenWanMin-' + weight + ' Cyrillic ' + template.type.name
        if old == dynamic_obj.path_id:
            tree['m_SourceFontFile'] = {'m_FileID': 0, 'm_PathID': font_ids[weight]}
            tree['m_FaceInfo'] = copy.deepcopy(original_tree['m_FaceInfo'])
            tree['m_CreationSettings']['pointSize'] = original_tree['m_CreationSettings']['pointSize']
            tree['m_IsMultiAtlasTexturesEnabled'] = True
        new.save_typetree(tree)
    original_tree['m_FallbackFontAssetTable'].insert(0, {'m_FileID': 0, 'm_PathID': references[dynamic_obj.path_id]})
    original_obj.save_typetree(original_tree)
    print('Added Cyrillic fallback using original typeface', weight, flush=True)
for obj in objects:
    if obj.type.name == 'TextAsset':
        asset = obj.read()
        draft = root / 'translation' / (asset.m_Name + '.json')
        if not draft.exists():
            continue
        translations = json.loads(draft.read_text(encoding='utf-8'))
        text = asset.m_Script
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        rows = list(reader)
        field = 'en' if 'en' in reader.fieldnames else 'textEN'
        for row in rows:
            if row.get(field) and row.get('id') in translations:
                value = translations[row['id']].replace('\u200b', '').replace('\ufeff', '')
                for old, new in [('Сайо', 'Саё'), ('Кою', 'Кои'), ('К-кой', 'К-Кои'), ('Менеджер', 'Управляющий'), ('менеджера', 'управляющего'), ('менеджеру', 'управляющему'), ('менеджером', 'управляющим'), ('менеджер', 'управляющий')]:
                    value = value.replace(old, new)
                row[field] = value
        buf = io.StringIO(newline='')
        writer = csv.DictWriter(buf, fieldnames=reader.fieldnames, lineterminator='\r\n')
        writer.writeheader()
        writer.writerows(rows)
        asset.m_Script = '\ufeff' + buf.getvalue()
        asset.save()
        stats[asset.m_Name] = len(translations)
        print('Translated', asset.m_Name, flush=True)
print('Saving bundle', flush=True)
source.write_bytes(env.file.save(packer='lz4'))
(output / 'build-report.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
print(stats, source.stat().st_size)

import zlib
from UnityPy.files.BundleFile import BundleFile
captured = []
read_fs = BundleFile.read_fs
def capture(self, reader):
    result = read_fs(self, reader)
    captured.append(zlib.crc32(result[1].bytes) & 0xffffffff)
    return result
BundleFile.read_fs = capture
UnityPy.load(str(original))
UnityPy.load(str(source))
assert len(captured) == 2
catalog = (game / data_name / 'StreamingAssets/aa/catalog.bin').read_bytes()
needle = struct.pack('<I', captured[0])
assert catalog.count(needle) == 1
(output / data_name / 'StreamingAssets/aa/catalog.bin').write_bytes(catalog.replace(needle, struct.pack('<I', captured[1])))
scene = UnityPy.load(str(game / data_name / 'data.unity3d'))
def encoded(text):
    data = text.encode('utf-8')
    return struct.pack('<I', len(data)) + data + b'\0' * (-len(data) % 4)
replacements = {'LOG': 'ЛОГ', 'AUTO': 'АВТО', 'SKIP': 'СКИП', 'SETTINGS': 'НАСТРОЙКИ'}
counts = dict.fromkeys(replacements, 0)
for obj in scene.objects:
    if obj.type.name != 'MonoBehaviour':
        continue
    raw = obj.get_raw_data()
    before = raw
    for old, new in replacements.items():
        counts[old] += raw.count(encoded(old))
        raw = raw.replace(encoded(old), encoded(new))
    if raw != before:
        obj.set_raw_data(raw)
assert all(value == 1 for value in counts.values())
(output / data_name / 'data.unity3d').write_bytes(scene.file.save(packer='lz4'))
