"""Owner-scoped review rounds live alongside, never inside, canonical study content."""
from datetime import datetime,timezone
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field


class ReviewAnswer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    index:int=Field(ge=0,strict=True)
    correct:bool=Field(strict=True)


class ReviewStart(BaseModel):
    model_config=ConfigDict(extra='forbid')
    new_round:bool=False
    content:dict|None=None


def fingerprint(content):
    raw=json.dumps({'items':content['items'],'mode':content['mode']},ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(raw.encode()).hexdigest()


class Reviews:
    def __init__(self,workspace):
        self.workspace=workspace
        with workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS review_rounds (
                id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),set_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,item_count INTEGER NOT NULL,created_at TEXT NOT NULL,completed_at TEXT)''')
            db.execute('CREATE INDEX IF NOT EXISTS review_rounds_deck ON review_rounds(user_id,set_id,content_hash,created_at)')
            db.execute('''CREATE TABLE IF NOT EXISTS review_answers (
                round_id TEXT NOT NULL REFERENCES review_rounds(id) ON DELETE CASCADE,
                item_index INTEGER NOT NULL,correct INTEGER NOT NULL,answered_at TEXT NOT NULL,
                PRIMARY KEY(round_id,item_index))''')

    def _snapshot(self,db,user_id,round_id):
        row=db.execute('SELECT * FROM review_rounds WHERE id=? AND user_id=?',(round_id,user_id)).fetchone()
        if not row:raise KeyError('Review round not found')
        result=dict(row);answers=[dict(r) for r in db.execute('SELECT item_index,correct FROM review_answers WHERE round_id=? ORDER BY item_index',(round_id,))]
        result['answers']=[{'index':a['item_index'],'correct':bool(a['correct'])} for a in answers]
        result['answered_count']=len(answers);result['correct_count']=sum(a['correct'] for a in answers)
        result['incorrect_count']=len(answers)-result['correct_count'];result['score_percent']=round(100*result['correct_count']/result['item_count'],1)
        history=[]
        for r in db.execute('''SELECT r.id,r.completed_at,r.item_count,COALESCE(SUM(a.correct),0) AS correct_count
            FROM review_rounds r LEFT JOIN review_answers a ON a.round_id=r.id
            WHERE r.user_id=? AND r.set_id=? AND r.content_hash=? AND r.completed_at IS NOT NULL
            GROUP BY r.id,r.completed_at,r.item_count ORDER BY r.completed_at DESC LIMIT 30''',(user_id,result['set_id'],result['content_hash'])):
            item=dict(r);item['score_percent']=round(100*item['correct_count']/item['item_count'],1);history.append(item)
        result['history']=history
        return result

    def start(self,user_id,set_id,content,new_round=False):
        if content['mode']!='flashcards' or not content['items']:raise ValueError('Choose a nonempty flashcard set.')
        digest=fingerprint(content);stamp=datetime.now(timezone.utc).isoformat()
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            # An unsaved ID cannot impersonate another account's persisted deck.
            foreign=db.execute('SELECT 1 FROM study_sets WHERE id=? AND owner_id<>?',(set_id,user_id)).fetchone()
            if foreign:raise KeyError('Study set not found')
            latest=db.execute('''SELECT id,completed_at FROM review_rounds WHERE user_id=? AND set_id=? AND content_hash=?
                ORDER BY created_at DESC,id DESC LIMIT 1''',(user_id,set_id,digest)).fetchone()
            # A second device requesting another round resumes any existing unfinished round.
            if latest and (not new_round or latest['completed_at'] is None):return self._snapshot(db,user_id,latest['id'])
            identifier=uuid4().hex
            db.execute('INSERT INTO review_rounds VALUES (?,?,?,?,?,?,?)',(identifier,user_id,set_id,digest,len(content['items']),stamp,None))
            return self._snapshot(db,user_id,identifier)

    def answer(self,user_id,round_id,answer):
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            round=db.execute('SELECT * FROM review_rounds WHERE id=? AND user_id=?',(round_id,user_id)).fetchone()
            if not round:raise KeyError('Review round not found')
            if answer.index>=round['item_count']:raise ValueError('This card is outside the review round.')
            old=db.execute('SELECT correct FROM review_answers WHERE round_id=? AND item_index=?',(round_id,answer.index)).fetchone()
            if old:
                if bool(old['correct'])!=answer.correct:raise HTTPException(409,'This card was already rated. Start a new round to rate it again.')
                return self._snapshot(db,user_id,round_id)
            if round['completed_at']:raise HTTPException(409,'This review round is complete.')
            stamp=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO review_answers VALUES (?,?,?,?)',(round_id,answer.index,int(answer.correct),stamp))
            count=db.execute('SELECT COUNT(*) FROM review_answers WHERE round_id=?',(round_id,)).fetchone()[0]
            if count==round['item_count']:db.execute('UPDATE review_rounds SET completed_at=? WHERE id=?',(stamp,round_id))
            return self._snapshot(db,user_id,round_id)
