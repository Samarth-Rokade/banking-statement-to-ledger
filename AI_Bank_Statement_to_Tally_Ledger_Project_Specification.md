# AI Bank Statement → Tally Ledger Generator

## Project Specification (v1.0)

> **Objective**
>
> Build a production-grade AI system that converts bank statements into
> Tally-compatible ledger entries with maximum accuracy. The scope of
> this project is **only** the Statement → Ledger workflow. Do not add
> unrelated accounting features.

------------------------------------------------------------------------

# Tech Stack

## Frontend

-   React
-   TypeScript
-   Tailwind CSS
-   TanStack Query
-   Zustand
-   React Hook Form

## Backend

-   FastAPI
-   SQLAlchemy
-   PostgreSQL
-   Alembic
-   Pydantic

## AI

-   Gemini 2.5 Pro
-   Gemini 2.5 Flash (optional for inexpensive operations)

## PDF Parsing

-   pdfplumber
-   Camelot
-   pandas
-   openpyxl

## OCR

-   PaddleOCR
-   Tesseract (fallback)

------------------------------------------------------------------------

# Product Goal

Convert:

Bank Statement (PDF/CSV/Excel)

↓

Extract Transactions

↓

Understand Narrations

↓

Identify Existing/New Ledger

↓

Assign Correct Group

↓

Generate Voucher

↓

Export Tally-Compatible Data

The primary goal is **accuracy**, not speed.

------------------------------------------------------------------------

# Success Metrics

  Metric                   Target
  ------------------------ --------
  Transaction extraction   100%
  Debit/Credit detection   100%
  Amount accuracy          100%
  Ledger prediction        \>98%
  Voucher prediction       \>98%
  Existing ledger match    \>99%
  Duplicate detection      100%
  Export validity          100%

------------------------------------------------------------------------

# Core Principle

Gemini must **never** process every transaction.

Pipeline:

Transaction → Rule Engine → Exact Ledger Match → Alias Match →
Similarity Match → Gemini → Human Review (only if needed)

------------------------------------------------------------------------

# High-Level Architecture

React

↓

FastAPI

↓

Statement Parser

↓

Transaction Extractor

↓

Normalization Engine

↓

Rule Engine

↓

Ledger Matching Engine

↓

AI Prediction Engine

↓

Validation Engine

↓

Voucher Generator

↓

Export

------------------------------------------------------------------------

# Development Modules

## Module 1 -- Authentication

JWT Authentication

Pages: - Login - Register

------------------------------------------------------------------------

## Module 2 -- Dashboard

Display: - Uploaded Statements - Processing Status - Total
Transactions - Auto Matched - AI Predicted - Manual Review Required -
Export Ready

------------------------------------------------------------------------

## Module 3 -- Upload Module

Supported Formats: - PDF - CSV - Excel

Workflow:

Upload

↓

Validate

↓

Store File

↓

Create Processing Job

↓

Parse

Never process synchronously inside the upload request.

------------------------------------------------------------------------

## Module 4 -- Statement Parser

Responsibility:

Convert statements into normalized transaction objects.

Output:

``` json
{
  "date":"",
  "description":"",
  "reference":"",
  "debit":0,
  "credit":0,
  "balance":0
}
```

No AI.

------------------------------------------------------------------------

## Module 5 -- Transaction Normalizer

Normalize bank-specific narrations.

Examples:

RTGS DR

RTGS-OUTWARD

RTGS

↓

RTGS_OUT

Also normalize:

-   UPI
-   IMPS
-   NEFT
-   Cash Deposit
-   ATM
-   Interest
-   Cheque
-   Charges

------------------------------------------------------------------------

## Module 6 -- Rule Engine

Deterministic mappings.

Examples:

BANK CHARGES → Bank Charges Ledger → Indirect Expenses

CASH DEP → Cash → Contra

INTEREST CREDIT → Interest Income

No AI.

------------------------------------------------------------------------

## Module 7 -- Ledger Database

Ledger table stores:

-   Ledger Name
-   Group
-   Aliases
-   Usage Count
-   Confidence

------------------------------------------------------------------------

## Module 8 -- Alias Engine

Match variations.

Example:

VCT PRODUCTS LTD

↓

VCT PRODUCTS

------------------------------------------------------------------------

## Module 9 -- Similarity Engine

Use:

-   pg_trgm
-   Levenshtein
-   Fuzzy Matching

Purpose:

Find similar ledger names before AI.

------------------------------------------------------------------------

## Module 10 -- AI Prediction Engine

Only receives unresolved transactions.

Prompt includes:

-   Transaction
-   Amount
-   Existing Ledgers
-   Ledger Groups
-   Similar Matches
-   Rules

Gemini must return JSON only.

Example:

``` json
{
  "ledger_name":"VCT PRODUCTS",
  "group":"Sundry Creditors",
  "voucher":"Payment",
  "confidence":98
}
```

------------------------------------------------------------------------

## Module 11 -- Validation Engine

Validate:

-   Ledger Exists
-   Group Exists
-   Voucher Exists
-   Debit/Credit Correct
-   Duplicate Detection

------------------------------------------------------------------------

## Module 12 -- Manual Review

Show only low-confidence predictions.

User actions:

-   Approve
-   Change Ledger
-   Change Group
-   Change Voucher

------------------------------------------------------------------------

## Module 13 -- Learning System

Whenever the user changes a prediction:

Narration

↓

Correct Ledger

↓

Store Mapping

↓

Reuse in future

The system should improve over time.

------------------------------------------------------------------------

## Module 14 -- Voucher Generator

Generate:

-   Receipt
-   Payment
-   Contra
-   Journal

Rule-based.

------------------------------------------------------------------------

## Module 15 -- Export

Generate:

-   Excel
-   CSV
-   Tally XML

Validate before export.

------------------------------------------------------------------------

# Backend Folder Structure

``` text
backend/
└── app/
    ├── auth/
    ├── upload/
    ├── parser/
    ├── normalizer/
    ├── rules/
    ├── ledger/
    ├── matcher/
    ├── ai/
    ├── validator/
    ├── vouchers/
    ├── export/
    ├── jobs/
    ├── models/
    ├── schemas/
    ├── services/
    ├── repositories/
    ├── prompts/
    ├── utils/
    ├── config/
    └── tests/
```

------------------------------------------------------------------------

# Frontend Pages

1.  Login
2.  Dashboard
3.  Upload Statement
4.  Processing Status
5.  Transactions
6.  Review Predictions
7.  Ledger Master
8.  Export

------------------------------------------------------------------------

# API Endpoints

POST /auth/login

POST /upload

GET /jobs/{id}

GET /transactions

POST /predict

POST /approve

GET /ledgers

POST /ledgers

GET /groups

POST /voucher

GET /export/xml

GET /export/excel

------------------------------------------------------------------------

# Database Tables

-   users
-   uploaded_files
-   processing_jobs
-   parsed_transactions
-   ledger_groups
-   ledgers
-   ledger_aliases
-   voucher_types
-   vouchers
-   ai_predictions
-   manual_corrections
-   rules
-   audit_logs

------------------------------------------------------------------------

# Prompt Strategy

Create dedicated prompts:

-   ledger_prediction.md
-   voucher_prediction.md
-   ledger_group_prediction.md
-   validation.md

Each prompt performs one task.

------------------------------------------------------------------------

# Accuracy Pipeline

Raw Transaction

↓

Statement Parsing

↓

Normalization

↓

Rule Engine

↓

Exact Ledger Match

↓

Alias Match

↓

Similarity Match

↓

Gemini Prediction

↓

Validation

↓

Manual Review (if confidence is low)

↓

Save Learned Mapping

↓

Export

------------------------------------------------------------------------

# Development Guidelines for Claude

1.  Build module-by-module.
2.  Maintain strict separation of concerns.
3.  Prefer deterministic logic over AI.
4.  Use Gemini only when earlier stages fail.
5.  Return structured JSON from AI.
6.  Write unit tests for every module.
7.  Keep business rules configurable.
8.  Make all parsers extensible for future banks.
9.  Use repository and service layers.
10. Optimize for correctness and maintainability before performance.
