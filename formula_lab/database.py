"""Transactional SQLite/PostgreSQL access; canonical payloads remain opaque text."""
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import psycopg

INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
WRITE_LOCK = 721604228


def secret(name, default=''):
    if os.getenv(name):
        return os.environ[name]
    path=os.getenv(name+'_FILE')
    return Path(path).read_text().strip() if path else default


def postgres_config():
    if os.getenv('DATABASE_URL'):
        return os.environ['DATABASE_URL']
    if os.getenv('MATHPDF_POSTGRES_HOST'):
        return psycopg.conninfo.make_conninfo(host=os.environ['MATHPDF_POSTGRES_HOST'],
            port=os.getenv('MATHPDF_POSTGRES_PORT','5432'),dbname=os.getenv('POSTGRES_DB','mathpdf'),
            user=os.getenv('POSTGRES_USER','mathpdf'),password=secret('POSTGRES_PASSWORD'),connect_timeout=10)
    return None


class Row(dict):
    def __getitem__(self,key):
        return tuple(self.values())[key] if isinstance(key,int) else super().__getitem__(key)


def rows(cursor):
    names=[column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names,values))


class EmptyCursor:
    rowcount=0
    def fetchone(self):return None
    def fetchall(self):return []
    def __iter__(self):return iter(())


def parameters(sql):
    # Convert only placeholders outside quoted SQL literals/identifiers; values stay bound.
    out=[];quoted=None;index=0
    while index<len(sql):
        char=sql[index]
        if quoted:
            out.append('%%' if char=='%' else char)
            if char==quoted:
                if index+1<len(sql) and sql[index+1]==quoted:
                    out.append(sql[index+1]);index+=1
                else:quoted=None
        elif char in {'\"',"'"}:quoted=char;out.append(char)
        elif char=='?':out.append('%s')
        elif char=='%':out.append('%%')
        else:out.append(char)
        index+=1
    return ''.join(out)


class PostgresConnection:
    def __init__(self, config):
        self.raw=psycopg.connect(config,row_factory=rows)
    def execute(self, sql, args=None):
        text=sql.strip().upper()
        if text.startswith('PRAGMA TABLE_INFO'):
            table=re.search(r'\((\w+)\)',sql).group(1)
            return self.raw.execute('SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position',(table,))
        if text.startswith('PRAGMA'):return EmptyCursor()
        if text=='BEGIN IMMEDIATE':return self.raw.execute('SELECT pg_advisory_xact_lock(%s)',(WRITE_LOCK,))
        if text=='BEGIN':return self.raw.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        return self.raw.execute(parameters(sql) if args is not None else sql,args)
    def executescript(self, sql):return self.raw.execute(sql)
    def close(self):self.raw.close()
    def __enter__(self):return self
    def __exit__(self,kind,error,traceback):
        if kind:self.raw.rollback()
        else:self.raw.commit()


class Database:
    def __init__(self, path):
        self.path=path;self.config=postgres_config();self.is_postgres=bool(self.config)
    @contextmanager
    def connection(self):
        db=PostgresConnection(self.config) if self.is_postgres else sqlite3.connect(self.path,timeout=10)
        if not self.is_postgres:
            db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()
    def initialize(self,db):
        if self.is_postgres:
            db.execute('''CREATE OR REPLACE FUNCTION json_extract(document text,path text) RETURNS text
                LANGUAGE sql IMMUTABLE AS $$ SELECT document::jsonb #>> string_to_array(substring(path FROM 3),'.') $$''')
    def cleanup_trigger(self,db,table,kind):
        if self.is_postgres:
            db.execute(f'''CREATE OR REPLACE FUNCTION {table}_organization_delete_fn() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN DELETE FROM library_items WHERE owner_id=OLD.owner_id
                AND kind='{kind}' AND item_id=OLD.id; RETURN OLD; END $$''')
            # CREATE OR REPLACE TRIGGER is supported by the pinned PostgreSQL version.
            db.execute(f'''CREATE OR REPLACE TRIGGER {table}_organization_delete AFTER DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION {table}_organization_delete_fn()''')
        else:
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_organization_delete AFTER DELETE ON {table}
                BEGIN DELETE FROM library_items WHERE owner_id=OLD.owner_id AND kind='{kind}' AND item_id=OLD.id; END''')
