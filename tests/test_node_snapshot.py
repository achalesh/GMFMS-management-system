import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User


class NodeSnapshotTests(TestCase):
    def test_export_preserves_source_and_keeps_credentials_out_of_logs(self):
        user = User.objects.create_user(username='snapshot-test', email='snapshot@example.invalid', password='synthetic-password-123')
        original_hash = user.password
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'snapshot'
            log = StringIO()
            call_command('export_node_snapshot', output=str(output), stdout=log)
            body = (output / 'snapshot.json').read_bytes()
            report = json.loads((output / 'reconciliation.json').read_text())
            self.assertEqual(hashlib.sha256(body).hexdigest(), report['snapshot_sha256'])
            self.assertEqual(report['counts']['accounts.user'], 1)
            self.assertFalse(report['source_modified'])
            self.assertNotIn(original_hash, log.getvalue())
            user.refresh_from_db()
            self.assertEqual(user.password, original_hash)
            self.assertEqual(User.objects.count(), 1)
            with self.assertRaises(CommandError):
                call_command('export_node_snapshot', output=str(output), stdout=log)
            self.assertEqual((output / 'snapshot.json').read_bytes(), body)
