"""Read-only, local demonstration API. No incident confirmation or automation endpoints."""
import os,sqlite3
from contextlib import closing
from pathlib import Path
from fastapi import FastAPI,HTTPException,Query
from pydantic import BaseModel
app=FastAPI(title='I23 Logs Quality & Triage — demo',version='1.0.0',description='Read-only. Synthetic fixture. Never use for automatic incident actions.')
class ServiceQuality(BaseModel):
    service:str
    quality_status:str
    count:int
class TriageSignal(BaseModel):
    service:str
    hour_utc:str
    signal:str
    error_rate:float
    evidence_events:int
    status:str
    is_confirmed_incident:bool

def db():
    path=Path(os.getenv('I23_DB_PATH','outputs/demo/quality.sqlite'))
    if not path.is_file():raise HTTPException(status_code=503,detail='Demo database unavailable')
    c=sqlite3.connect(f'file:{path.resolve()}?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    return c
@app.get('/health')
def health():return {'service':'I23-READ_ONLY','database_configured':Path(os.getenv('I23_DB_PATH','outputs/demo/quality.sqlite')).is_file()}
@app.get('/quality',response_model=list[ServiceQuality])
def quality():
    with closing(db()) as c:return [dict(r) for r in c.execute('SELECT service, quality_status, count FROM quality_by_service ORDER BY service,quality_status')]
@app.get('/triage',response_model=list[TriageSignal])
def triage(service:str|None=Query(None,max_length=64),limit:int=Query(50,ge=1,le=200)):
    with closing(db()) as c:
        if service:rows=c.execute('SELECT * FROM alerts WHERE service=? ORDER BY hour_utc LIMIT ?', (service,limit)).fetchall()
        else:rows=c.execute('SELECT * FROM alerts ORDER BY hour_utc,service LIMIT ?', (limit,)).fetchall()
    return [dict(r) for r in rows]
