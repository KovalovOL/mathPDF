"""Credential redaction and bounded, explicit diagnostic truncation."""
import json
import re
import os

SENSITIVE=re.compile(r'(^|[_-])(authorization|cookie|set.cookie|password|passwd|secret|api.key|access.token|refresh.token|id.token|client.secret|verifier|nonce|oauth.code|private.key)($|[_-])',re.I)
KEY_VALUE=re.compile(r'\b(sk-(?:proj-)?[A-Za-z0-9_-]{12,}|GOCSPX-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._~+/-]{12,})',re.I)
PEM=re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----')
MAX_CONTEXT_BYTES=2*1024*1024


def sanitize(value,depth=0):
    if depth>24:return {'_truncated':'nesting limit'}
    if isinstance(value,dict):
        def sensitive(key):
            normalized=re.sub(r'[^a-z0-9]','',str(key).casefold())
            return SENSITIVE.search(str(key)) or normalized in {'authorization','cookie','cookies','setcookie','token','code','state','key','credentials'} or any(part in normalized for part in ['password','passwd','secret','apikey','accesstoken','refreshtoken','idtoken','privatekey','accesskey','secter','verifier','nonce'])
        return {str(k)[:200]:'[REDACTED]' if sensitive(k) or (k=='input' and any(sensitive(part) for part in value.get('loc',[]) if isinstance(part,str))) else sanitize(v,depth+1) for k,v in list(value.items())[:500]}
    if isinstance(value,(list,tuple)):
        result=[sanitize(v,depth+1) for v in value[:300]]
        if len(value)>300:result.append({'_truncated':len(value)-300,'reason':'list limit'})
        return result
    if isinstance(value,str):
        clean=KEY_VALUE.sub('[REDACTED]',PEM.sub('[REDACTED PRIVATE KEY]',value))
        for key,secret in os.environ.items():
            if len(secret)>=12 and re.search(r'KEY|SECRET|PASSWORD|TOKEN|DATABASE_URL',key,re.I):clean=clean.replace(secret,'[REDACTED]')
        return clean if len(clean)<=250000 else clean[:250000]+'\n[TRUNCATED: string limit]'
    if value is None or isinstance(value,(int,float,bool)):return value
    return str(type(value).__name__)


def bounded(value,max_bytes=MAX_CONTEXT_BYTES):
    clean=sanitize(value)
    encoded=json.dumps(clean,ensure_ascii=False).encode()
    if len(encoded)<=max_bytes:return clean
    # Preserve an explicit bounded serialized prefix; never silently pretend it is complete.
    return {'_truncated':True,'original_bytes':len(encoded),'reason':'diagnostic byte limit',
            'serialized_prefix':encoded[:max_bytes-300].decode('utf-8',errors='ignore')}
