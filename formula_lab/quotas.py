"""Transactional UTC daily allowances, including compatible historical settings."""
from datetime import datetime,timedelta,timezone
import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import AliasChoices,BaseModel,ConfigDict,Field

DEFAULT_DAILY_TOKENS=200_000


class QuotaExceeded(ValueError):
    def __init__(self,message,allowance,reason='exhausted',estimate=None):
        super().__init__(message)
        self.allowance,self.reason,self.estimate=allowance,reason,estimate

    def payload(self):
        limit=self.allowance['daily_tokens']
        return {'detail':str(self),'code':'generation_limit','reason':self.reason,'allowance':self.allowance,
            'required_percent':round(100*self.estimate/limit,1) if self.estimate is not None and limit else None}


class DefaultAllowance(BaseModel):
    model_config=ConfigDict(extra='forbid')
    daily_tokens:int=Field(ge=0,le=1_000_000_000,strict=True,validation_alias=AliasChoices('daily_tokens','monthly_tokens'))


class UserAllowance(BaseModel):
    model_config=ConfigDict(extra='forbid')
    daily_tokens:int|None=Field(ge=0,le=1_000_000_000,strict=True,validation_alias=AliasChoices('daily_tokens','monthly_tokens'))


def period(now=None):
    now=now or datetime.now(timezone.utc)
    now=now.astimezone(timezone.utc)
    start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    end=start+timedelta(days=1)
    return start.isoformat(),end.isoformat()


class GenerationQuota:
    def __init__(self,workspace):
        self.workspace=workspace
        with workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS generation_limits (
                scope TEXT PRIMARY KEY,monthly_tokens BIGINT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT)''')
            columns={r['name'] for r in db.execute('PRAGMA table_info(generation_limits)')}
            if 'daily_tokens' not in columns:db.execute('ALTER TABLE generation_limits ADD COLUMN daily_tokens BIGINT')
            db.execute('''CREATE TABLE IF NOT EXISTS generation_reservations (
                attempt_id TEXT PRIMARY KEY REFERENCES ai_usage(id),user_id TEXT NOT NULL REFERENCES users(id),
                period_start TEXT NOT NULL,tokens BIGINT NOT NULL,state TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS generation_reservations_user ON generation_reservations(user_id,period_start)')
            db.execute('''INSERT INTO generation_limits (scope,monthly_tokens,updated_at,updated_by,daily_tokens)
                VALUES (?,?,?,?,?) ON CONFLICT(scope) DO NOTHING''',
                ('default',DEFAULT_DAILY_TOKENS,datetime.now(timezone.utc).isoformat(),None,DEFAULT_DAILY_TOKENS))

    def _status(self,db,user_id,now=None):
        start,end=period(now)
        role=db.execute("SELECT COALESCE(r.role,'free') AS role FROM users u LEFT JOIN user_roles r ON r.user_id=u.id WHERE u.id=?",(user_id,)).fetchone()
        if not role:raise KeyError('User not found')
        # The owner explicitly changed the policy to daily. Keep legacy values
        # untouched, adopting their configured amounts only when no daily value exists.
        default=db.execute("SELECT COALESCE(daily_tokens,monthly_tokens) FROM generation_limits WHERE scope='default'").fetchone()[0]
        override=db.execute('SELECT COALESCE(daily_tokens,monthly_tokens) FROM generation_limits WHERE scope=?',('user:'+user_id,)).fetchone()
        limit=override[0] if override else default
        used=db.execute('''SELECT COALESCE(SUM(input_tokens+output_tokens),0) FROM ai_usage
            WHERE user_id=? AND started_at>=? AND started_at<? AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL''',(user_id,start,end)).fetchone()[0]
        held=db.execute('''SELECT COALESCE(SUM(r.tokens),0) FROM generation_reservations r JOIN ai_usage a ON a.id=r.attempt_id
            WHERE r.user_id=? AND a.started_at>=? AND a.started_at<? AND r.state IN ('reserved','unknown')
            AND (a.input_tokens IS NULL OR a.output_tokens IS NULL)''',(user_id,start,end)).fetchone()[0]
        remaining=max(0,limit-used-held)
        return {'limited':role['role']=='free','daily_tokens':limit,'default_daily_tokens':default,
            'override_daily_tokens':override[0] if override else None,'used_tokens':used,'reserved_tokens':held,
            'remaining_percent':round(100*remaining/limit,1) if limit else 0,'remaining_tokens':remaining,
            'period_start':start,'resets_at':end,'reset_interval_seconds':86400,'timezone':'UTC'}

    def status(self,user_id):
        with self.workspace.connection() as db:return self._status(db,user_id)

    def check(self,user_id):
        state=self.status(user_id)
        if state['limited'] and state['remaining_tokens']<=0:
            disabled=state['daily_tokens']==0
            raise QuotaExceeded('Your free plan currently has no generation allowance.' if disabled else
                'Your daily generation allowance is used up. It renews at 00:00 UTC.',state,'disabled' if disabled else 'exhausted')
        return state

    def reserve(self,db,attempt_id,user_id,estimate,now=None):
        state=self._status(db,user_id,now)
        if not state['limited']:return
        estimate=max(1,int(estimate))
        if state['remaining_tokens']<estimate:
            reason='disabled' if state['daily_tokens']==0 else 'exhausted' if state['remaining_tokens']==0 else 'insufficient'
            raise QuotaExceeded('There is not enough daily generation allowance for this request. Choose fewer pages or items.',state,reason,estimate)
        db.execute('INSERT INTO generation_reservations VALUES (?,?,?,?,?)',(attempt_id,user_id,state['period_start'],estimate,'reserved'))

    @staticmethod
    def settle(db,attempt_id,known,unbilled=False):
        db.execute('UPDATE generation_reservations SET state=? WHERE attempt_id=?',('settled' if known else 'released' if unbilled else 'unknown',attempt_id))

    def settings(self):
        with self.workspace.connection() as db:return {'daily_tokens':db.execute("SELECT COALESCE(daily_tokens,monthly_tokens) FROM generation_limits WHERE scope='default'").fetchone()[0],'reset_interval_seconds':86400,'timezone':'UTC'}

    def update(self,actor,daily_tokens,user_id=None):
        stamp=datetime.now(timezone.utc).isoformat();scope='user:'+user_id if user_id else 'default'
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            role=db.execute('SELECT role FROM user_roles WHERE user_id=?',(actor.id,)).fetchone()
            if not role or role['role'] not in {'owner','admin'}:raise HTTPException(403,'Administrator access is required.')
            if user_id and not db.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone():raise KeyError('User not found')
            old=db.execute('SELECT COALESCE(daily_tokens,monthly_tokens) FROM generation_limits WHERE scope=?',(scope,)).fetchone()
            if daily_tokens is None:
                if not user_id:raise ValueError('The default allowance requires a value.')
                db.execute('DELETE FROM generation_limits WHERE scope=?',(scope,))
            else:
                if isinstance(daily_tokens,bool) or not isinstance(daily_tokens,int) or not 0<=daily_tokens<=1_000_000_000:raise ValueError('Invalid token allowance.')
                db.execute('''INSERT INTO generation_limits (scope,monthly_tokens,updated_at,updated_by,daily_tokens) VALUES (?,?,?,?,?)
                    ON CONFLICT(scope) DO UPDATE SET daily_tokens=excluded.daily_tokens,
                    updated_at=excluded.updated_at,updated_by=excluded.updated_by''',(scope,daily_tokens,stamp,actor.id,daily_tokens))
            db.execute('INSERT INTO admin_audit VALUES (?,?,?,?,?)',(uuid4().hex,actor.id,'generation_allowance',
                json.dumps({'scope':scope,'old':old[0] if old else None,'new':daily_tokens,'period':'utc_day'}),stamp))
        return self.status(user_id) if user_id else self.settings()
