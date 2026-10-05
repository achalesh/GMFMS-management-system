"""Read-only, private migration evidence; never modifies the Django source."""
import base64
import hashlib
import json
import os
from pathlib import Path

from django.apps import apps
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Export a private Node migration snapshot and non-sensitive reconciliation report.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        output = Path(options['output']).resolve()
        if output.exists():
            raise CommandError('Output directory already exists; choose a new snapshot directory.')
        selected = {'accounts', 'locations', 'organization', 'registrations', 'facilitators', 'idcards', 'audit'}
        records, files, counts = [], {}, {}
        try:
            with transaction.atomic():
                if connection.vendor == 'postgresql':
                    with connection.cursor() as cursor:
                        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                elif connection.vendor != 'sqlite':
                    raise CommandError('This exporter currently supports SQLite/PostgreSQL source snapshots only.')
                for model in sorted(apps.get_models(), key=lambda m: m._meta.label_lower):
                    if model._meta.app_label not in selected or model._meta.model_name == 'requestbudget':
                        continue
                    objects = list(model.objects.order_by('pk'))
                    counts[model._meta.label_lower] = len(objects)
                    records.extend(json.loads(serializers.serialize('json', objects)))
                    for obj in objects:
                        for field in model._meta.fields:
                            if field.get_internal_type() != 'FileField':
                                continue
                            value = getattr(obj, field.name)
                            if not value:
                                continue
                            key = f'{model._meta.label_lower}:{obj.pk}:{field.name}'
                            digest = hashlib.sha256()
                            chunks = []
                            with value.storage.open(value.name, 'rb') as stream:
                                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                                    digest.update(chunk)
                                    chunks.append(chunk)
                            body = b''.join(chunks)
                            expected = getattr(obj, {'file': 'sha256', 'pdf': 'pdf_sha256', 'print_pdf': 'print_sha256'}.get(field.name, ''), None)
                            if expected and expected != digest.hexdigest():
                                raise CommandError('A stored artifact failed its SHA-256 integrity check. Source is unchanged.')
                            files[key] = {'name': value.name, 'size': len(body), 'sha256': digest.hexdigest(), 'body': base64.b64encode(body).decode('ascii')}
            snapshot = {'format': 'gramaswaraj-django-snapshot-v1', 'created_at': timezone.now().isoformat(), 'records': records, 'files': files}
            body = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            report = {'format': snapshot['format'], 'counts': counts, 'artifact_count': len(files), 'artifact_bytes': sum(f['size'] for f in files.values()), 'snapshot_sha256': hashlib.sha256(body).hexdigest(), 'source_modified': False}
            output.mkdir(parents=True, mode=0o700)
            for name, content in [('snapshot.json', body), ('reconciliation.json', json.dumps(report, indent=2).encode('utf-8'))]:
                with os.fdopen(os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                    stream.write(content)
            self.stdout.write(self.style.SUCCESS(f'Snapshot verified: {len(records)} records and {len(files)} artifacts. Source unchanged. Keep snapshot.json private.'))
        except CommandError:
            raise
        except Exception as error:
            raise CommandError('Snapshot export failed. No source records were changed; check source artifact availability.') from error
