\set ON_ERROR_STOP on

DROP DATABASE IF EXISTS bank_oltp;
DROP DATABASE IF EXISTS bank_dw;
CREATE DATABASE bank_oltp;
CREATE DATABASE bank_dw;

\connect bank_oltp
\ir oltp_schema.sql
\ir ../data/sql/01_client.sql
\ir ../data/sql/02_account.sql
\ir ../data/sql/03_disp.sql
\ir ../data/sql/04_loan.sql
\ir ../data/sql/05_trans.sql

\connect bank_dw
\ir dw_schema.sql