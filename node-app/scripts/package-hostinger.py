"""Local packaging only. Run from node-app with Python; no Python needed on hosting."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib, json

root = Path(__file__).resolve().parent.parent
target = root / 'release'
target.mkdir(exist_ok=True)
files = []
for directory in ['src', 'scripts', 'test', 'views', 'public', 'assets', 'data']:
    for path in sorted((root / directory).rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Symbolic links are not permitted in the deployment package')
        if path.is_file() and '__pycache__' not in path.parts:
            files.append(path)
for name in ['package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'README.md', 'HOSTINGER.md', 'MIGRATION.md', '.env.production.example']:
    files.append(root / name)
manifest = {}
with ZipFile(target / 'gramaswaraj-hostinger.zip', 'w', ZIP_DEFLATED) as archive:
    for path in files:
        name = path.relative_to(root).as_posix()
        if not path.resolve().is_relative_to(root):
            raise RuntimeError('File outside application root')
        body = path.read_bytes()
        archive.writestr(name, body)
        manifest[name] = hashlib.sha256(body).hexdigest()
    archive.writestr('release-manifest.json', json.dumps(manifest, indent=2))
with ZipFile(target / 'gramaswaraj-hostinger.zip') as archive:
    assert archive.testzip() is None
    assert 'package.json' in archive.namelist()
    assert not any(name == '.env' or name.startswith(('var/', 'node_modules/', '.pnpm-store/')) for name in archive.namelist())
print(f'Packaged and verified {len(files)} files: release/gramaswaraj-hostinger.zip')
