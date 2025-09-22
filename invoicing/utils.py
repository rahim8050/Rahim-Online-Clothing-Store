from __future__ import annotations


import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

from django.conf import settings
from django.core import signing
from django.http import FileResponse

from pathlib import Path

from django.conf import settings



def generate_signed_download_token(invoice_id: int, expires_seconds: int = 300) -> str:
    signer = signing.TimestampSigner()
    value = f"inv:{invoice_id}"
    return signer.sign(value)


def verify_signed_download_token(token: str, max_age: int = 300) -> int:
    signer = signing.TimestampSigner()
    value = signer.unsign(token, max_age=max_age)
    assert value.startswith("inv:")
    return int(value.split(":", 1)[1])


def ensure_invoice_pdf_path(invoice_id: int) -> str:
    media_root = getattr(settings, "MEDIA_ROOT", Path.cwd() / "mediafiles")
    outdir = Path(media_root) / "invoices"
    outdir.mkdir(parents=True, exist_ok=True)
    return str(outdir / f"invoice_{invoice_id}.pdf")
