import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime_config import load_configuration


class RuntimeConfigTests(unittest.TestCase):
    def test_root_env_loads_and_process_environment_wins(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder)
            (root / 'local_invoice').mkdir()
            (root / '.env').write_text('GOOGLE_CLIENT_ID=root-client\nGOOGLE_CLIENT_SECRET=root-secret\n')
            (root / 'local_invoice' / '.env').write_text('GOOGLE_CLIENT_ID=legacy\nGOOGLE_REDIRECT_URI=http://127.0.0.1:8089/auth/google/callback\n')
            os.environ['GOOGLE_CLIENT_SECRET'] = 'process-secret'
            load_configuration(root)
            self.assertEqual(os.environ['GOOGLE_CLIENT_ID'], 'root-client')
            self.assertEqual(os.environ['GOOGLE_CLIENT_SECRET'], 'process-secret')
            self.assertEqual(os.environ['GOOGLE_REDIRECT_URI'], 'http://127.0.0.1:8089/auth/google/callback')
