"""Transactional monthly free allowances; canonical provider observations stay intact."""
from datetime import datetime,timezone
import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field

DEFAULT_MONTHLY_TOKENS=200_000


class QuotaExceeded(ValueError):
    pass


class DefaultAllowance(BaseModel):
    model_config=ConfigDict(extra='forbid')
    monthly_tokens:int=Field(ge=0,le=1_000_000_000,strict=True)


class UserAllowance(BaseModel):
    model_config=ConfigDict(extra='forbid')
    monthly_tokens:int|None=Field(ge=0,le=1_000_000_000,strict=True)


def period(now=None):
    now=now or datetime.now(timezone.utc)
    start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    return start.isoformat(),end.isoformat()


class GenerationQuota:
    def __init__(self,workspace):
        self.workspace=workspace
        with workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS generation_limits (
                scope TEXT PRIMARY KEY,monthly_tokens BIGINT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS generation_reservations (
                attempt_id TEXT PRIMARY KEY REFERENCES ai_usage(id),user_id TEXT NOT NULL REFERENCES users(id),
                period_start TEXT NOT NULL,tokens BIGINT NOT NULL,state TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS generation_reservations_user ON generation_reservations(user_id,period_start)')
            db.execute('INSERT INTO generation_limits VALUES (?,?,?,?) ON CONFLICT(scope) DO NOTHING',
                ('default',DEFAULT_MONTHLY_TOKENS,datetime.now(timezone.utc).isoformat(),None))

    def _status(self,db,user_id,now=None):
        start,end=period(now)
        role=db.execute("SELECT COALESCE(r.role,'free') AS role FROM users u LEFT JOIN user_roles r ON r.user_id=u.id WHERE u.id=?",(user_id,)).fetchone()
        if not role:raise KeyError('User not found')
        default=db.execute("SELECT monthly_tokens FROM generation_limits WHERE scope='default'").fetchone()[0]
        override=db.execute('SELECT monthly_tokens FROM generation_limits WHERE scope=?',('user:'+user_id,)).fetchone()
        limit=override[0] if override else default
        used=db.execute('''SELECT COALESCE(SUM(input_tokens+output_tokens),0) FROM ai_usage
            WHERE user_id=? AND started_at>=? AND started_at<? AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL''',(user_id,start,end)).fetchone()[0]
        held=db.execute('''SELECT COALESCE(SUM(r.tokens),0) FROM generation_reservations r JOIN ai_usage a ON a.id=r.attempt_id
            WHERE r.user_id=? AND r.period_start=? AND r.state IN ('reserved','unknown')
            AND (a.input_tokens IS NULL OR a.output_tokens IS NULL)''',(user_id,start)).fetchone()[0]
        remaining=max(0,limit-used-held)
        return {'limited':role['role']=='free','monthly_tokens':limit,'default_monthly_tokens':default,
            'override_monthly_tokens':override[0] if override else None,'used_tokens':used,'reserved_tokens':held,
            'remaining_percent':round(100*remaining/limit,1) if limit else 0,'remaining_tokens':remaining,
            'period_start':start,'resets_at':end}

    def status(self,user_id):
        with self.workspace.connection() as db:return self._status(db,user_id)

    def check(self,user_id):
        state=self.status(user_id)
        if state['limited'] and state['remaining_tokens']<=0:
            raise QuotaExceeded('Your monthly generation allowance is used up. It renews on '+state['resets_at'][:10]+' (UTC).')
        return state

    def reserve(self,db,attempt_id,user_id,estimate):
        state=self._status(db,user_id)
        if not state['limited']:return
        estimate=max(1,int(estimate))
        if state['remaining_tokens']<estimate:
            raise QuotaExceeded('There is not enough generation allowance for this request. Choose fewer pages or items, or wait until '+state['resets_at'][:10]+' (UTC).')
        db.execute('INSERT INTO generation_reservations VALUES (?,?,?,?,?)',(attempt_id,user_id,state['period_start'],estimate,'reserved'))

    @staticmethod
    def settle(db,attempt_id,known,unbilled=False):
        db.execute('UPDATE generation_reservations SET state=? WHERE attempt_id=?',('settled' if known else 'released' if unbilled else 'unknown',attempt_id))

    def settings(self):
        with self.workspace.connection() as db:return {'monthly_tokens':db.execute("SELECT monthly_tokens FROM generation_limits WHERE scope='default'").fetchone()[0]}

    def update(self,actor,monthly_tokens,user_id=None):
        stamp=datetime.now(timezone.utc).isoformat();scope='user:'+user_id if user_id else 'default'
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            role=db.execute('SELECT role FROM user_roles WHERE user_id=?',(actor.id,)).fetchone()
            if not role or role['role'] not in {'owner','admin'}:raise HTTPException(403,'Administrator access is required.')
            if user_id and not db.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone():raise KeyError('User not found')
            old=db.execute('SELECT monthly_tokens FROM generation_limits WHERE scope=?',(scope,)).fetchone()
            if monthly_tokens is None:
                if not user_id:raise ValueError('The default allowance requires a value.')
                db.execute('DELETE FROM generation_limits WHERE scope=?',(scope,))
            else:
                if isinstance(monthly_tokens,bool) or not isinstance(monthly_tokens,int) or not 0<=monthly_tokens<=1_000_000_000:raise ValueError('Invalid token allowance.')
                db.execute('''INSERT INTO generation_limits VALUES (?,?,?,?) ON CONFLICT(scope) DO UPDATE SET
                    monthly_tokens=excluded.monthly_tokens,updated_at=excluded.updated_at,updated_by=excluded.updated_by''',(scope,monthly_tokens,stamp,actor.id))
            db.execute('INSERT INTO admin_audit VALUES (?,?,?,?,?)',(uuid4().hex,actor.id,'generation_allowance',
                json.dumps({'scope':scope,'old':old[0] if old else None,'new':monthly_tokens}),stamp))
        return self.status(user_id) if user_id else self.settings()
