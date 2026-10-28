"""Persistent secret bootstrap and the private Garage container launcher."""
import json
import os
from pathlib import Path
import secrets
import sys


def initialize(directory:Path):
    directory.mkdir(parents=True,exist_ok=True);directory.chmod(0o700)
    values={'postgres-password':secrets.token_urlsafe(48),'garage-rpc':secrets.token_hex(32),
        's3.json':json.dumps({'access_key_id':'GK'+secrets.token_hex(16),'secret_access_key':secrets.token_hex(32),
                            'bucket':'mathpdf','region':'garage'})}
    for name,value in values.items():
        path=directory/name
        try:
            with path.open('x') as target:target.write(value+'\n')
            path.chmod(0o600)
        except FileExistsError:pass
    print('Persistent infrastructure secrets are ready; existing values retained.')


def main():
    if len(sys.argv)>1 and sys.argv[1]=='garage':
        creds=json.loads(Path(os.environ['MATHPDF_S3_CREDENTIALS_FILE']).read_text())
        os.environ.update(GARAGE_DEFAULT_ACCESS_KEY=creds['access_key_id'],GARAGE_DEFAULT_SECRET_KEY=creds['secret_access_key'],GARAGE_DEFAULT_BUCKET=creds['bucket'])
        os.execv('/usr/local/bin/garage',['garage','server','--single-node','--default-bucket'])
    initialize(Path(os.getenv('MATHPDF_SECRETS_DIR','/run/mathpdf-secrets')))

if __name__=='__main__':main()
