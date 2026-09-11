"""Load installation configuration without depending on the launch directory."""
from pathlib import Path
from dotenv import load_dotenv


def load_configuration(root=None):
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    # Process environment wins, then project .env, then the legacy local file.
    load_dotenv(root / '.env', override=False)
    load_dotenv(root / 'local_invoice' / '.env', override=False)
