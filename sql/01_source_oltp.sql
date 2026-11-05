-- =====================================================================
-- SUMBER 1: PostgreSQL (sistem OLTP core banking)
-- Database : bank_oltp
-- Tabel    : client, account, disp, loan, trans
-- (district, card, order disimpan sebagai file CSV = SUMBER 2)
-- =====================================================================

DROP TABLE IF EXISTS trans  CASCADE;
DROP TABLE IF EXISTS loan   CASCADE;
DROP TABLE IF EXISTS disp   CASCADE;
DROP TABLE IF EXISTS account CASCADE;
DROP TABLE IF EXISTS client CASCADE;

-- district_id tidak diberi FK karena tabel district ada di sumber CSV
CREATE TABLE client (
    client_id    INTEGER PRIMARY KEY,
    gender       CHAR(1)  NOT NULL CHECK (gender IN ('M','F')),
    birth_date   DATE     NOT NULL,
    district_id  INTEGER  NOT NULL
);

CREATE TABLE account (
    account_id   INTEGER PRIMARY KEY,
    district_id  INTEGER     NOT NULL,
    frequency    VARCHAR(30) NOT NULL,
    date         DATE        NOT NULL
);

CREATE TABLE disp (
    disp_id      INTEGER PRIMARY KEY,
    client_id    INTEGER     NOT NULL REFERENCES client(client_id),
    account_id   INTEGER     NOT NULL REFERENCES account(account_id),
    type         VARCHAR(15) NOT NULL
);

CREATE TABLE loan (
    loan_id      INTEGER PRIMARY KEY,
    account_id   INTEGER       NOT NULL REFERENCES account(account_id),
    date         DATE          NOT NULL,
    amount       INTEGER       NOT NULL,
    duration     INTEGER       NOT NULL,
    payments     NUMERIC(12,2) NOT NULL,
    status       CHAR(1)       NOT NULL
);

CREATE TABLE trans (
    trans_id     INTEGER PRIMARY KEY,
    account_id   INTEGER     NOT NULL REFERENCES account(account_id),
    date         DATE        NOT NULL,
    type         VARCHAR(10) NOT NULL,
    operation    VARCHAR(20),
    amount       INTEGER     NOT NULL,
    balance      INTEGER     NOT NULL,
    k_symbol     VARCHAR(15),
    bank         CHAR(2),
    account      BIGINT
);

CREATE INDEX idx_disp_account  ON disp(account_id);
CREATE INDEX idx_trans_account ON trans(account_id, date);
CREATE INDEX idx_loan_account  ON loan(account_id);
