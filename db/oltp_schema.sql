DROP TABLE IF EXISTS trans, loan, disp, account, client CASCADE;

CREATE TABLE client (
    client_id    INTEGER PRIMARY KEY,
    gender       CHAR(1) NOT NULL,
    birth_date   DATE NOT NULL,
    district_id  INTEGER NOT NULL
);

CREATE TABLE account (
    account_id   INTEGER PRIMARY KEY,
    district_id  INTEGER NOT NULL,
    frequency    VARCHAR(30) NOT NULL,
    date         DATE NOT NULL
);

CREATE TABLE disp (
    disp_id      INTEGER PRIMARY KEY,
    client_id    INTEGER NOT NULL REFERENCES client(client_id),
    account_id   INTEGER NOT NULL REFERENCES account(account_id),
    type         VARCHAR(10) NOT NULL
);

CREATE TABLE loan (
    loan_id      INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES account(account_id),
    date         DATE NOT NULL,
    amount       INTEGER NOT NULL,
    duration     INTEGER NOT NULL,
    payments     NUMERIC(12,2) NOT NULL,
    status       CHAR(1) NOT NULL
);

CREATE TABLE trans (
    trans_id     INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES account(account_id),
    date         DATE NOT NULL,
    type         VARCHAR(10) NOT NULL,
    operation    VARCHAR(20),
    amount       NUMERIC(14,2) NOT NULL,
    balance      NUMERIC(14,2) NOT NULL,
    k_symbol     VARCHAR(20),
    bank         VARCHAR(5),
    account      BIGINT
);