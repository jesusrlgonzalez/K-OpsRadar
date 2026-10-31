-- I23 SQLite analytics: redacted fields only; schema in src/i23/store.py
SELECT service,quality_status,COUNT(*) FROM events GROUP BY service,quality_status;
SELECT service,hour_utc,error_rate,http_5xx FROM windows WHERE count>=8 ORDER BY error_rate DESC LIMIT 20;
SELECT service,hour_utc,signal,status,is_confirmed_incident FROM alerts ORDER BY hour_utc,service;
