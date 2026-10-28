"""Persistent roles, verified owner bootstrap and audited owner-only grants."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

OWNER_EMAIL='sasha.kovalov2008@gmail.com'
Role=Literal['free','premium','admin','owner']


def now():return datetime.now(timezone.utc).isoformat()


class RoleChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    role:Literal['free','premium','admin']


class Roles:
    def __init__(self,workspace):
        self.workspace=workspace
        with workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.executescript('''CREATE TABLE IF NOT EXISTS user_roles (
                user_id TEXT PRIMARY KEY REFERENCES users(id),role TEXT NOT NULL,
                updated_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS single_owner ON user_roles(role) WHERE role='owner';
                CREATE TABLE IF NOT EXISTS role_audit (
                id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,target_id TEXT NOT NULL,
                old_role TEXT NOT NULL,new_role TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS admin_audit (id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,action TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);''')
            candidate=db.execute('SELECT id FROM users WHERE LOWER(email)=? ORDER BY updated_at DESC LIMIT 1',(OWNER_EMAIL,)).fetchone()
            if candidate:self._owner(db,candidate['id'])
    @staticmethod
    def _owner(db,identifier):
        current=db.execute("SELECT user_id FROM user_roles WHERE role='owner'").fetchone()
        if current:return
        db.execute('''INSERT INTO user_roles VALUES (?,?,?) ON CONFLICT(user_id)
            DO UPDATE SET role=excluded.role,updated_at=excluded.updated_at''',(identifier,'owner',now()))
    def verified_login(self,identifier,email):
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if email.casefold()==OWNER_EMAIL:self._owner(db,identifier)
            else:db.execute('INSERT INTO user_roles VALUES (?,?,?) ON CONFLICT(user_id) DO NOTHING',(identifier,'free',now()))
    def role(self,identifier):
        with self.workspace.connection() as db:
            row=db.execute('SELECT role FROM user_roles WHERE user_id=?',(identifier,)).fetchone()
        return row['role'] if row else 'free'
    def require_admin(self,user):
        if not user or self.role(user.id) not in {'admin','owner'}:
            raise HTTPException(403,'Administrator access is required.')
    def change(self,actor,target,new_role):
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            role=db.execute('SELECT role FROM user_roles WHERE user_id=?',(actor.id,)).fetchone()
            if not role or role['role']!='owner':raise HTTPException(403,'Only the owner can change account roles.')
            if not db.execute('SELECT 1 FROM users WHERE id=?',(target,)).fetchone():raise KeyError('User not found')
            old=db.execute('SELECT role FROM user_roles WHERE user_id=?',(target,)).fetchone();old_role=old['role'] if old else 'free'
            if old_role=='owner':raise HTTPException(400,'Owner access cannot be changed here.')
            if new_role not in {'free','premium','admin'}:raise ValueError('Invalid account role.')
            stamp=now()
            db.execute('''INSERT INTO user_roles VALUES (?,?,?) ON CONFLICT(user_id)
                DO UPDATE SET role=excluded.role,updated_at=excluded.updated_at''',(target,new_role,stamp))
            db.execute('INSERT INTO role_audit VALUES (?,?,?,?,?,?)',(uuid4().hex,actor.id,target,old_role,new_role,stamp))
        return {'user_id':target,'role':new_role}
