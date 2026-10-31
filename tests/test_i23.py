"""Synthetic contract, replay, privacy and authority tests. Never assert real-world validity."""
import csv,hashlib,json,os,sqlite3,tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from i23 import audit,api,fixture,gates,ml_baseline,store,loghub_adapter
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'DATOS_FUENTES/04_SINTETICOS/logs_dirty.csv'
RESULTS=ROOT/'outputs/demo'
class TestLogQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.out=Path(cls.tmp.name)
        cls.report=audit.audit(RAW,cls.out)
        store.build(cls.out,cls.out/'x.sqlite')
        with (cls.out/'decisions.csv').open(newline='',encoding='utf-8') as f:cls.rows=list(csv.DictReader(f))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_input_size(self):self.assertEqual(self.report['input_rows'],2400)
    def test_conservation(self):self.assertTrue(self.report['conservation_pass']);self.assertEqual(sum(self.report['dispositions'].values()),2400)
    def test_three_categories(self):self.assertEqual(set(self.report['dispositions']),{'CANDIDATE','REVIEW','QUARANTINE'})
    def test_quarantine_invalid_date(self):self.assertIn('INVALID_EVENT_TIME',next(r for r in self.rows if r['ingest_id']=='ING-00012')['reasons'])
    def test_quarantine_no_service(self):self.assertEqual(next(r for r in self.rows if r['ingest_id']=='ING-00059')['quality_status'],'QUARANTINE')
    def test_negative_duration(self):self.assertIn('NEGATIVE_DURATION',next(r for r in self.rows if r['ingest_id']=='ING-00022')['reasons'])
    def test_conflicting_duplicates(self):self.assertIn('DUPLICATE_ID_CONFLICT',next(r for r in self.rows if r['ingest_id']=='ING-00105')['reasons'])
    def test_late_event_review(self):self.assertIn('OBSERVED_LATE',next(r for r in self.rows if r['ingest_id']=='ING-00009')['reasons'])
    def test_clock_skew(self):self.assertIn('SOURCE_CLOCK_SKEW',next(r for r in self.rows if r['ingest_id']=='ING-00028')['reasons'])
    def test_unknown_schema(self):self.assertIn('UNSUPPORTED_SCHEMA',next(r for r in self.rows if r['ingest_id']=='ING-00144')['reasons'])
    def test_trace_invalid(self):self.assertIn('INVALID_TRACE_CONTEXT',next(r for r in self.rows if r['ingest_id']=='ING-00051')['reasons'])
    def test_out_of_order_late(self):self.assertIn('EVENT_BEFORE_WATERMARK',next(r for r in self.rows if r['ingest_id']=='ING-00849')['reasons'])
    def test_secret_is_redacted(self):
        data=(self.out/'decisions.csv').read_text()
        self.assertNotIn('fake.analyst@corp.test',data);self.assertNotIn('FAKE-SECRET-DO-NOT-USE',data);self.assertNotIn('192.0.2.20',data)
        self.assertIn('[REDACTED_SECRET]',data)
    def test_truth_separate(self):
        data=(self.out/'decisions.csv').read_text();self.assertNotIn('injected_issue',data)
    def test_checksum_of_raw(self):self.assertEqual(hashlib.sha256(RAW.read_bytes()).hexdigest(),self.report['source_sha256'])
    def test_alerts_not_confirmed(self):
        with (self.out/'triage_alerts.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        self.assertGreaterEqual(len(rows),1)
        self.assertTrue(all(x['is_confirmed_incident']=='False' and x['status']=='TRIAGE_ONLY' for x in rows))
    def test_no_loss_to_outputs(self):self.assertEqual(len(self.rows),2400)
    def test_blank_timezone_rejected(self):self.assertIsNone(audit.dt('2026-02-01T03:00:00'))
    def test_valid_timezone_accepted(self):self.assertEqual(audit.dt('2026-02-01T03:00:00-06:00').hour,9)
    def test_nonfinite_duration_rejected(self):
        row={k:'ok' for k in fixture.FIELDS};row.update({'ingest_id':'x','event_id':'e','timestamp':'2026-02-01T00:00:00+00:00','observed_timestamp':'2026-02-01T00:00:01+00:00','service':'api-gateway','host':'h','severity':'INFO','http_status':'200','duration_ms':'nan','trace_id':'0'*32,'span_id':'0'*16,'schema_version':'v1','message':'hi'})
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'x.csv';audit.write_csv(f,[row],fixture.FIELDS);r=audit.audit(f,Path(t)/'out')
            self.assertEqual(r['issues_count_by_reason']['INVALID_DURATION'],1)
    def test_fixture_is_deterministic(self):
        with tempfile.TemporaryDirectory() as t:
            fixture.create(t)
            self.assertEqual(hashlib.sha256((Path(t)/'logs_dirty.csv').read_bytes()).hexdigest(),self.report['source_sha256'])
    def test_fixture_injections_all_reviewed(self):
        with (ROOT/'DATOS_FUENTES/04_SINTETICOS/INJECTION_TRUTH_NOT_FOR_TRAINING.csv').open(newline='',encoding='utf-8') as f:truth=list(csv.DictReader(f))
        self.assertEqual(len(truth),41)
        flagged={r['ingest_id'] for r in self.rows if r['quality_status']!='CANDIDATE'}
        self.assertTrue({r['ingest_id'] for r in truth}.issubset(flagged))
    def test_store_row_count(self):
        count=store.build(self.out,self.out/'x.sqlite');self.assertEqual(count,2400)
        with sqlite3.connect(self.out/'x.sqlite') as c:self.assertEqual(c.execute('SELECT SUM(count) FROM quality_by_service').fetchone()[0],2400)
    def test_empty_gate_blocks(self):self.assertEqual(gates.evaluate(ROOT,'G1')['status'],'BLOCK')
    def test_no_automatic_gate_authority(self):self.assertFalse(gates.evaluate(ROOT,'G5_TECH')['automatic_authority'])
    def test_gate_reviewer_separation(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'EVIDENCIAS/G1';p.mkdir(parents=True)
            (p/'approval.json').write_text(json.dumps({'gate':'G1','status':'APPROVED','owner':'same','independent_reviewer':'same','evidence_sha256':'0'*64,'approved_at':'2026-01-01T00:00:00Z'}))
            self.assertEqual(gates.evaluate(t,'G1')['status'],'BLOCK')
    def test_model_split_chronological(self):
        with (self.out/'window_metrics.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        tr,te,edge=ml_baseline.split_windows(rows)
        self.assertLessEqual(max(x['hour_utc'] for x in tr),edge)
        self.assertGreater(min(x['hour_utc'] for x in te),edge)
    def test_ml_report_exploratory(self):
        result=ml_baseline.run(self.out/'window_metrics.csv',self.out/'experiment.json')
        self.assertEqual(result['experiment'],'EXPLORATORY_SYNTHETIC_ONLY')
        self.assertGreater(result['test_windows'],0)
    def test_api_health(self):
        os.environ['I23_DB_PATH']=str(self.out/'x.sqlite')
        with TestClient(api.app) as c:self.assertTrue(c.get('/health').json()['database_configured'])
    def test_api_quality_read_only(self):
        os.environ['I23_DB_PATH']=str(self.out/'x.sqlite')
        with TestClient(api.app) as c:
            x=c.get('/quality');self.assertEqual(x.status_code,200);self.assertEqual(sum(k['count'] for k in x.json()),2400)
            self.assertEqual(c.post('/quality').status_code,405)
    def test_api_triage_no_incident(self):
        os.environ['I23_DB_PATH']=str(self.out/'x.sqlite')
        with TestClient(api.app) as c:
            x=c.get('/triage');self.assertEqual(x.status_code,200);self.assertTrue(all(not k['is_confirmed_incident'] for k in x.json()))
            self.assertEqual(c.get('/triage?limit=999').status_code,422)
    def test_api_sql_injection_parameterized(self):
        os.environ['I23_DB_PATH']=str(self.out/'x.sqlite')
        with TestClient(api.app) as c:self.assertEqual(c.get('/triage?service=%27%20OR%201=1%20--').json(),[])
    def test_bgl_domain_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'BGL_subset.log';f.write_text('- sample nonalert\nKERNEL_WARN sample alert category\n')
            r=loghub_adapter.profile_bgl(f,Path(t)/'profile.json')
            self.assertEqual(r['marked_alert'],1);self.assertEqual(r['marked_nonalert'],1)
            self.assertFalse(r['http_mapping_supported']);self.assertFalse(r['raw_copied'])
    def test_bgl_missing_source_denied(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileNotFoundError):loghub_adapter.profile_bgl(Path(t)/'missing',Path(t)/'out.json')
    def test_no_real_sources_claimed(self):self.assertEqual(json.loads((ROOT/'DATOS_FUENTES/04_SINTETICOS/SOURCE_PROVENANCE.json').read_text())['not_real_incidents'],True)
if __name__=='__main__':unittest.main()
