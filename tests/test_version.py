# Maintainer: Leandro Michelino | ACE | leandro.michelino@oracle.com
import re

from src.version import VERSION_LABEL, __version__


def test_project_version_uses_semantic_mvp_format():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)
    assert VERSION_LABEL == f"v{__version__}"
