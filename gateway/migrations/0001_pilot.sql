PRAGMA foreign_keys = ON;
-- Inference responses expire after 15 minutes; a scheduled job clears ciphertext.
CREATE TABLE accounts (
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','suspended')),
  balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
  held INTEGER NOT NULL DEFAULT 0 CHECK(held >= 0 AND held <= balance),
  created INTEGER NOT NULL
);
CREATE TABLE devices (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
  secret_hash TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'pending'
    CHECK(status IN ('pending','active','revoked')),
  kind TEXT NOT NULL DEFAULT 'signup' CHECK(kind IN ('signup','recovery')),
  claimed_name TEXT NOT NULL, claimed_phone TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL
);
CREATE INDEX devices_account ON devices(account_id, status);
CREATE TABLE payments (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
  device_id TEXT NOT NULL REFERENCES devices(id), utr TEXT NOT NULL UNIQUE,
  amount_paise INTEGER NOT NULL DEFAULT 1500 CHECK(amount_paise = 1500),
  credits INTEGER NOT NULL DEFAULT 1000000 CHECK(credits = 1000000),
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
  created INTEGER NOT NULL, reviewed INTEGER, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX payments_account ON payments(account_id, created DESC);
CREATE INDEX payments_pending ON payments(status, created);
CREATE UNIQUE INDEX payments_one_pending ON payments(account_id) WHERE status='pending';
CREATE TABLE ledger (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
  delta INTEGER NOT NULL, kind TEXT NOT NULL, reference TEXT NOT NULL UNIQUE,
  created INTEGER NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ledger_account ON ledger(account_id, created DESC);
CREATE TABLE requests (
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
  payload_hash TEXT NOT NULL, reserve INTEGER NOT NULL CHECK(reserve > 0),
  state TEXT NOT NULL CHECK(state IN ('inflight','succeeded','failed','uncertain','resolved')),
  prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
  charged INTEGER NOT NULL DEFAULT 0 CHECK(charged >= 0),
  response_cipher TEXT, http_status INTEGER NOT NULL DEFAULT 202,
  created INTEGER NOT NULL, completed INTEGER, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX requests_active ON requests(state, created);
CREATE INDEX requests_account ON requests(account_id, state, created);
CREATE TABLE admin_sessions (hash TEXT PRIMARY KEY, expires INTEGER NOT NULL);
CREATE TABLE rate_windows (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE audit (id TEXT PRIMARY KEY, action TEXT NOT NULL, reference TEXT NOT NULL, created INTEGER NOT NULL, note TEXT NOT NULL);
CREATE INDEX requests_cached_expiry ON requests(completed) WHERE response_cipher IS NOT NULL;
CREATE INDEX sessions_expiry ON admin_sessions(expires);
CREATE INDEX rates_expiry ON rate_windows(expires);
CREATE INDEX audit_created ON audit(created DESC);
-- Credits and holds are changed only by state transitions inside SQLite transactions.
CREATE TRIGGER payment_credit AFTER UPDATE OF status ON payments
WHEN OLD.status = 'pending' AND NEW.status = 'approved'
BEGIN
  INSERT INTO ledger VALUES ('payment:'||NEW.id, NEW.account_id, NEW.credits, 'payment', 'payment:'||NEW.id, NEW.reviewed, NEW.utr);
  UPDATE accounts SET balance=balance+NEW.credits, status='active' WHERE id=NEW.account_id AND status!='suspended';
  SELECT CASE WHEN changes()!=1 THEN RAISE(ABORT,'Account is suspended') END;
  UPDATE devices SET status='active' WHERE id=NEW.device_id AND status='pending' AND kind='signup';
END;
CREATE TRIGGER request_hold AFTER INSERT ON requests
WHEN NEW.state='inflight'
BEGIN
  UPDATE accounts SET held=held+NEW.reserve WHERE id=NEW.account_id;
END;
CREATE TRIGGER request_settle AFTER UPDATE OF state ON requests
WHEN OLD.state IN ('inflight','uncertain') AND NEW.state IN ('succeeded','failed','resolved')
BEGIN
  SELECT CASE WHEN NEW.charged > OLD.reserve THEN RAISE(ABORT,'Usage exceeds reservation') END;
  UPDATE accounts SET held=held-OLD.reserve, balance=balance-NEW.charged WHERE id=NEW.account_id;
  INSERT INTO ledger VALUES ('request:'||NEW.id, NEW.account_id, -NEW.charged, 'usage', 'request:'||NEW.id, NEW.completed, NEW.note);
END;
CREATE TRIGGER payment_final BEFORE UPDATE OF status ON payments
WHEN OLD.status != 'pending' AND NEW.status != OLD.status
BEGIN SELECT RAISE(ABORT,'Payment already reviewed'); END;
CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT,'Ledger is immutable'); END;
CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger BEGIN SELECT RAISE(ABORT,'Ledger is immutable'); END;
