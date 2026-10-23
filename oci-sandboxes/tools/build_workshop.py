"""Check lab code against source files and build the learner ZIP."""
import argparse
import json
import re
from pathlib import Path
from textwrap import dedent
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'files' / 'sandboxes-workshop'
ARCHIVE = SOURCE.with_suffix('.zip')
FILES = (
    'setup.sh', 'configure.py', 'cloud_auth.py', 'generate_policy.py',
    'sandbox_access.py', 'read_csv.py', 'analysis.py', 'requirements.txt',
    'prepare_agent.py', 'run_agent.py', 'monthly-financials.csv',
    'prepare_web.py', 'web_app.py',
)
BLOCK = re.compile(r'^([ ]*)```(python|python3|py|bash|sh)[ \t]*\n(.*?)^\1```[ \t]*$', re.M | re.S)


def lab_files():
    manifest = ROOT / 'workshops' / 'tenancy' / 'manifest.json'
    tutorials = json.loads(manifest.read_text())['tutorials']
    return [manifest.parent / item['filename'] for item in tutorials]


def is_excerpt(snippet, source):
    lines = source.splitlines(keepends=True)
    size = len(snippet.splitlines())
    return bool(snippet.strip()) and any(
        dedent(''.join(lines[start:start + size])) == snippet
        for start in range(len(lines) - size + 1))


def check_snippets(files):
    count = 0
    for lab in lab_files():
        content = lab.read_text()
        for block in BLOCK.finditer(content):
            code = dedent(''.join(line for line in block[3].splitlines(keepends=True)
                                  if line.strip() not in ('<copy>', '</copy>')))
            location = f'{lab.resolve().relative_to(ROOT)}:{content.count(chr(10), 0, block.start()) + 1}'
            if block[2] in ('bash', 'sh'):
                missing = set(re.findall(r'[\w-]+\.(?:py|sh)\b', code)) - files.keys()
                if missing:
                    raise ValueError(f'{location}: command refers to unpackaged files: {sorted(missing)}')
            else:
                marker = re.search(r'<!-- source: ([\w-]+\.py) -->$', content[:block.start()].rstrip())
                if not marker or marker[1] not in files:
                    raise ValueError(f'{location}: Python snippet needs a source comment naming a packaged file.')
                if not is_excerpt(code, files[marker[1]].decode()):
                    raise ValueError(f'{location}: Python snippet differs from {marker[1]}.')
                count += 1
    print(f'PASS: {count} Python excerpts match source; shell commands reference packaged scripts.')


def check_archive(files, archive=ARCHIVE):
    expected = {f'{SOURCE.name}/{name}': data for name, data in files.items()}
    with ZipFile(archive) as bundle:
        if sorted(bundle.namelist()) != sorted(expected):
            raise ValueError('ZIP contains missing, extra or duplicate entries.')
        for name, data in expected.items():
            if bundle.read(name) != data:
                raise ValueError(f'ZIP differs from source: {name}')
    print(f'PASS: all {len(files)} ZIP entries match source byte-for-byte.')


def build_archive(files):
    temporary = ARCHIVE.with_suffix('.zip.tmp')
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED) as bundle:
            for name, data in files.items():
                bundle.writestr(f'{SOURCE.name}/{name}', data)
        check_archive(files, temporary)
        temporary.replace(ARCHIVE)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='Rebuild the ZIP after snippets pass.')
    args = parser.parse_args()
    sources = {'monthly-financials.csv': ROOT / 'files' / 'monthly-financials.csv'}
    files = {name: sources.get(name, SOURCE / name).read_bytes() for name in FILES}
    check_snippets(files)
    if args.build:
        build_archive(files)
    else:
        check_archive(files)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, BadZipFile) as error:
        raise SystemExit(f'FAIL: {error}')
