import shutil
import tempfile

import pytest
from django.conf import settings


@pytest.fixture(scope="session", autouse=True)
def temp_media_root():
    original_media_root = settings.MEDIA_ROOT
    new_media_root = tempfile.mkdtemp()
    settings.MEDIA_ROOT = new_media_root

    yield

    settings.MEDIA_ROOT = original_media_root
    shutil.rmtree(new_media_root)
