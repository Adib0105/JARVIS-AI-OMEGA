"""Record resolved components, license metadata and installed RECORD hashes.

This is a machine-readable inventory, not a claim of legal license approval or
reproducible signed binaries. Unknown license metadata remains explicitly unknown.
"""
import argparse
from datetime import datetime, timezone
from importlib.metadata import distributions
import json
import platform
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args = parser.parse_args()
components = []
for dist in sorted(distributions(), key=lambda d: d.metadata['Name'].lower()):
    files = []
    for item in dist.files or []:
        if item.hash:
            files.append({'path': str(item), 'algorithm': item.hash.mode, 'digest': item.hash.value})
    meta = dist.metadata
    license_value = meta.get('License-Expression') or meta.get('License') or 'UNKNOWN'
    components.append({'name': meta['Name'], 'version': dist.version, 'license_metadata': license_value[:4000],
                       'requires_python': meta.get('Requires-Python'), 'file_hashes': files,
                       'purl': 'pkg:pypi/' + meta['Name'].lower().replace('_', '-') + '@' + dist.version})
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
with open(args.output, 'w', encoding='utf-8') as out:
    json.dump({'schema': 'jarvis-dependency-inventory-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
               'commit': commit, 'platform': platform.platform(), 'python': platform.python_version(),
               'license_review': 'REQUIRES_OPERATOR_REVIEW', 'components': components}, out, indent=2)
