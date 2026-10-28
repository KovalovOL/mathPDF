"""Verified, restartable SQLite-to-PostgreSQL and local-to-Garage migration.

Run with application writes stopped. Original files and the SQLite backup are retained.
Canonical payloads are copied verbatim; this module never decodes study-set content.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from .workspace import Workspace
from .auth import Authentication, AuthConfig
from .library import Library
from .usage import Usage
from .reports import Reports
from .reviews import Reviews

MIGRATION_ID='sqlite-to-postgres-v1'
# Parents precede children; folders are additionally inserted topologically.
TABLES=['users','documents','study_sets','document_edits','sessions','oauth_flows',
        'library_folders','library_items','user_roles','role_audit','admin_audit',
        'model_prices','ai_usage','request_events','reports','generation_limits','generation_reservations','review_rounds','review_answers']
IDENTIFIER=re.compile(r'^[a-z_][a-z0-9_]*$')


def digest_rows(rows):
    encoded=sorted(json.dumps(list(r),ensure_ascii=False,separators=(',',':')) for r in rows)
    return hashlib.sha256(('\n'.join(encoded)).encode()).hexdigest()


def read_snapshot(path):
    with sqlite3.connect(path) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables-set(TABLES):raise ValueError('Migration stopped: an unsupported source table needs an explicit migration.')
        result={}
        for table in TABLES:
            if table not in tables:continue
            columns=[r[1] for r in db.execute(f'PRAGMA table_info({table})')]
            if any(not IDENTIFIER.fullmatch(c) for c in columns):raise ValueError('Migration stopped: invalid source column.')
            if table in {'documents','study_sets'} and 'owner_id' not in columns:
                raise ValueError('Migration stopped: legacy unowned data requires an explicit ownership migration.')
            rows=[tuple(r) for r in db.execute(f'SELECT * FROM {table}')]
            result[table]={'columns':columns,'rows':rows,'count':len(rows),'sha256':digest_rows(rows)}
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity check failed.')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('SQLite foreign-key check failed.')
    return result


def ordered_rows(table,entry):
    rows=entry['rows']
    if table!='library_folders':return rows
    indices={c:i for i,c in enumerate(entry['columns'])};pending=list(rows);done=set();ordered=[]
    while pending:
        ready=[r for r in pending if r[indices['parent_id']] is None or r[indices['parent_id']] in done]
        if not ready:raise ValueError('Migration stopped: cyclic or missing folder parent.')
        ordered.extend(ready);done.update(r[indices['id']] for r in ready);pending=[r for r in pending if r not in ready]
    return ordered


def migrate(directory):
    directory=Path(directory).resolve();workspace=Workspace(directory)
    if not workspace.db.is_postgres or not workspace.storage.remote:
        raise ValueError('Migration requires PostgreSQL and private object storage configuration.')
    Authentication(workspace,AuthConfig.from_environment());Library(workspace);Usage(workspace);Reports(workspace);Reviews(workspace)
    with workspace.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS migration_runs (id TEXT PRIMARY KEY,completed_at TEXT NOT NULL,manifest TEXT NOT NULL)')
        completed=db.execute('SELECT manifest FROM migration_runs WHERE id=?',(MIGRATION_ID,)).fetchone()
        if completed:
            print('Migration already completed; PostgreSQL remains authoritative.');return json.loads(completed['manifest'])
    source=directory/'workspace.sqlite3';backup_root=directory/'migration-backups';backup_root.mkdir(exist_ok=True);backup_root.chmod(0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=backup_root/('workspace-'+stamp+'.sqlite3')
    if source.exists():
        with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as original,sqlite3.connect(backup) as target:original.backup(target)
        backup.chmod(0o600);snapshot=read_snapshot(backup)
    else:
        if any(workspace.files.rglob('*')):raise ValueError('Migration stopped: local files exist without their SQLite database.')
        snapshot={}
    manifest={'version':1,'source_backup':str(backup) if source.exists() else None,
              'tables':{name:{k:v for k,v in entry.items() if k!='rows'} for name,entry in snapshot.items()},'objects':[]}
    # Retain every managed binary, including older, unreferenced immutable revisions.
    for path in sorted(workspace.files.rglob('*')):
        if not path.is_file():continue
        if path.is_symlink() or not path.resolve().is_relative_to(workspace.files.resolve()):
            raise ValueError('Migration stopped: managed binary storage contains a symbolic link.')
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest();key='documents/'+path.relative_to(workspace.files).as_posix()
        workspace.storage.put(key,data);workspace.storage.verify(key,sha)
        manifest['objects'].append({'key':key,'sha256':sha,'bytes':len(data)})
    available={obj['key']:obj for obj in manifest['objects']}
    documents=snapshot.get('documents',{'columns':[],'rows':[]})
    for values in documents['rows']:
        document=dict(zip(documents['columns'],values));obj=available.get('documents/'+document['stored_name'])
        if not obj or obj['sha256']!=document['sha256'] or obj['bytes']!=document['size']:
            raise ValueError('Migration stopped: a source document is missing or its bytes do not match the database.')
    with workspace.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        # A restart can never overwrite a database that has accepted new production writes.
        if db.execute('SELECT 1 FROM migration_runs WHERE id=?',(MIGRATION_ID,)).fetchone():
            raise ValueError('Migration completed concurrently; rerun to read its manifest.')
        for table in TABLES:
            if table in {'model_prices','generation_limits'}:continue  # deterministic defaults are seeded before import
            if db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:
                raise ValueError('Migration stopped: the target is not empty and has no completion marker.')
        for table,entry in snapshot.items():
            columns=entry['columns'];destination={r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
            if set(columns)-destination:raise ValueError('Migration stopped: a source column is not supported by the target.')
            names=','.join('"'+c+'"' for c in columns);bindings=','.join('?' for _ in columns)
            if table in {'model_prices','generation_limits'} and entry['rows']:db.execute(f'DELETE FROM {table}')
            for values in ordered_rows(table,entry):db.execute(f'INSERT INTO {table} ({names}) VALUES ({bindings})',values)
            # Read the same columns back, including raw payload strings, before the transaction commits.
            actual=db.execute(f'SELECT {names} FROM {table}').fetchall()
            if digest_rows([tuple(r[c] for c in columns) for r in actual])!=entry['sha256']:
                raise ValueError('Migration stopped: destination row verification failed.')
        db.execute('INSERT INTO migration_runs VALUES (?,?,?)',(MIGRATION_ID,datetime.now(timezone.utc).isoformat(),json.dumps(manifest,ensure_ascii=False)))
    # Owner bootstrap is additive and happens only after the exact imported rows have been verified.
    Authentication(workspace,AuthConfig.from_environment())
    marker=backup_root/'postgres-migration.json';temporary=marker.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));temporary.chmod(0o600);temporary.replace(marker)
    print(f'Migration verified: {sum(e["count"] for e in manifest["tables"].values())} rows, {len(manifest["objects"])} objects; originals and backup retained.')
    return manifest


def main():migrate(Path(os.getenv('MATHPDF_DATA_DIR','/app/.formula-lab')))
if __name__=='__main__':main()
