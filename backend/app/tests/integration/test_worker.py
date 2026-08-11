from app.jobs.worker import (
    apply_ai_prediction_job,
    apply_ledger_matching_job,
    apply_validation_job,
    claim_next_ai_predicting_job,
    claim_next_matching_job,
    claim_next_normalizing_job,
    claim_next_queued_job,
    claim_next_validating_job,
    normalize_job,
    process_job,
)
from app.models.ledger_group import LedgerGroup
from app.models.processing_job import JobStatus
from app.models.rule import Rule, RuleType
from app.models.uploaded_file import FileType
from app.normalizer.narration_normalizer import TransactionTypeTag
from app.repositories.job_repository import JobRepository
from app.repositories.parsed_transaction_repository import ParsedTransactionRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.repositories.user_repository import UserRepository
from app.repositories.voucher_repository import VoucherRepository
from app.repositories.voucher_type_repository import VoucherTypeRepository
from app.schemas.user import UserCreate


def _create_uploaded_file(db_session, tmp_path, filename: str, content: bytes, file_type: FileType):
    user = UserRepository(db_session).create(
        UserCreate(email="parser-test@example.com", password="s3cret-pass", full_name="Tester"),
        hashed_password="not-a-real-hash",
    )
    file_path = tmp_path / filename
    file_path.write_bytes(content)
    return UploadedFileRepository(db_session).create(
        user_id=user.id,
        original_filename=filename,
        storage_path=str(file_path),
        file_type=file_type,
        file_size_bytes=len(content),
        checksum_sha256="irrelevant-for-this-test",
    )


def test_claim_next_queued_job_returns_none_when_empty(db_session):
    assert claim_next_queued_job(db_session) is None


def test_process_job_parses_csv_and_marks_normalizing(db_session, tmp_path):
    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n"
        "01-01-2026,UPI-SWIGGY,250.00,0,9750.00\n"
    ).encode()
    uploaded_file = _create_uploaded_file(db_session, tmp_path, "statement.csv", csv_content, FileType.CSV)
    job = JobRepository(db_session).create(uploaded_file.id)

    claimed = claim_next_queued_job(db_session)
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.PARSING

    process_job(db_session, claimed)

    db_session.refresh(claimed)
    assert claimed.status == JobStatus.NORMALIZING
    assert claimed.total_transactions == 1

    transactions = ParsedTransactionRepository(db_session).list_for_job(job.id)
    assert len(transactions) == 1
    assert transactions[0].original_narration == "UPI-SWIGGY"


def test_claim_next_normalizing_job_returns_none_when_empty(db_session):
    assert claim_next_normalizing_job(db_session) is None


def test_normalize_job_tags_transactions_and_advances_to_matching(db_session, tmp_path):
    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n"
        "01-01-2026,CASH DEP-SELF- BRANCH,0,9750.00,9750.00\n"
        "02-01-2026,RTGS DR-REF12345 -SAMPLE VENDOR LIMITED -HDFC0000021,50000,0,-40250.00\n"
    ).encode()
    uploaded_file = _create_uploaded_file(db_session, tmp_path, "statement.csv", csv_content, FileType.CSV)
    job = JobRepository(db_session).create(uploaded_file.id)

    process_job(db_session, claim_next_queued_job(db_session))

    claimed = claim_next_normalizing_job(db_session)
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.MATCHING

    normalize_job(db_session, claimed)

    transactions = ParsedTransactionRepository(db_session).list_for_job(job.id)
    by_tag = {t.transaction_type_tag: t.normalized_narration for t in transactions}
    assert by_tag[TransactionTypeTag.CASH_DEPOSIT] == "CASH DEPOSIT"
    assert by_tag[TransactionTypeTag.RTGS_OUT] == "SAMPLE VENDOR LIMITED"


def test_claim_next_matching_job_returns_none_when_empty(db_session):
    assert claim_next_matching_job(db_session) is None


def test_apply_ledger_matching_resolves_cash_deposit_and_advances_to_ai_predicting(db_session, tmp_path):
    db_session.add(LedgerGroup(name="Cash-in-Hand", tally_group_type="Cash-in-Hand"))
    db_session.add(
        Rule(rule_type=RuleType.TAG, pattern="CASH_DEPOSIT", ledger_name="Cash", group_name="Cash-in-Hand", priority=100)
    )
    db_session.commit()

    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n"
        "01-01-2026,CASH DEP-SELF- BRANCH,0,9750.00,9750.00\n"
        "02-01-2026,RTGS DR-REF12345 -SAMPLE VENDOR LIMITED -HDFC0000021,50000,0,-40250.00\n"
    ).encode()
    uploaded_file = _create_uploaded_file(db_session, tmp_path, "statement.csv", csv_content, FileType.CSV)
    job = JobRepository(db_session).create(uploaded_file.id)

    process_job(db_session, claim_next_queued_job(db_session))
    normalize_job(db_session, claim_next_normalizing_job(db_session))

    claimed = claim_next_matching_job(db_session)
    assert claimed is not None
    assert claimed.status == JobStatus.AI_PREDICTING

    apply_ledger_matching_job(db_session, claimed)

    db_session.refresh(claimed)
    assert claimed.auto_matched_count == 1  # only the CASH_DEPOSIT row; RTGS_OUT is left unresolved

    transactions = ParsedTransactionRepository(db_session).list_for_job(job.id)
    resolved = [t for t in transactions if t.transaction_type_tag == TransactionTypeTag.CASH_DEPOSIT]
    unresolved = [t for t in transactions if t.transaction_type_tag == TransactionTypeTag.RTGS_OUT]
    assert resolved[0].ledger_id is not None
    assert unresolved[0].ledger_id is None


def test_apply_ledger_matching_falls_through_to_exact_match(db_session, tmp_path):
    # No rule matches RTGS_OUT, but a ledger with the exact extracted counterparty
    # name already exists - the waterfall should fall through Rule Engine to Exact
    # Match rather than leaving it unresolved.
    from app.models.ledger import Ledger, LedgerCreatedVia

    group = LedgerGroup(name="Sundry Creditors", tally_group_type="Sundry Creditors")
    db_session.add(group)
    db_session.flush()
    db_session.add(Ledger(name="SAMPLE VENDOR LIMITED", group_id=group.id, created_via=LedgerCreatedVia.MANUAL))
    db_session.commit()

    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n"
        "02-01-2026,RTGS DR-REF12345 -SAMPLE VENDOR LIMITED -HDFC0000021,50000,0,-40250.00\n"
    ).encode()
    uploaded_file = _create_uploaded_file(db_session, tmp_path, "statement.csv", csv_content, FileType.CSV)
    JobRepository(db_session).create(uploaded_file.id)

    process_job(db_session, claim_next_queued_job(db_session))
    normalize_job(db_session, claim_next_normalizing_job(db_session))
    claimed = claim_next_matching_job(db_session)

    apply_ledger_matching_job(db_session, claimed)

    db_session.refresh(claimed)
    assert claimed.auto_matched_count == 1
    transactions = ParsedTransactionRepository(db_session).list_for_job(claimed.id)
    assert transactions[0].resolution_source.value == "EXACT_MATCH"


def test_claim_next_validating_job_returns_none_when_empty(db_session):
    assert claim_next_validating_job(db_session) is None


def test_pipeline_reaches_ready_when_everything_resolves(db_session, tmp_path):
    db_session.add(LedgerGroup(name="Cash-in-Hand", tally_group_type="Cash-in-Hand"))
    db_session.add(
        Rule(rule_type=RuleType.TAG, pattern="CASH_DEPOSIT", ledger_name="Cash", group_name="Cash-in-Hand", priority=100)
    )
    db_session.commit()

    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n"
        "01-01-2026,CASH DEP-SELF- BRANCH,0,9750.00,9750.00\n"
    ).encode()
    uploaded_file = _create_uploaded_file(db_session, tmp_path, "statement.csv", csv_content, FileType.CSV)
    job = JobRepository(db_session).create(uploaded_file.id)

    process_job(db_session, claim_next_queued_job(db_session))
    normalize_job(db_session, claim_next_normalizing_job(db_session))
    apply_ledger_matching_job(db_session, claim_next_matching_job(db_session))
    apply_ai_prediction_job(db_session, claim_next_ai_predicting_job(db_session))

    claimed = claim_next_validating_job(db_session)
    assert claimed is not None
    assert claimed.status == JobStatus.REVIEW_REQUIRED  # provisional, overridden below on success

    apply_validation_job(db_session, claimed)

    db_session.refresh(claimed)
    assert claimed.status == JobStatus.READY
    assert claimed.manual_review_count == 0
    assert claimed.export_ready_count == 1
    assert claimed.completed_at is not None

    transactions = ParsedTransactionRepository(db_session).list_for_job(job.id)
    assert transactions[0].validation_errors is None

    # Module 14: a Cash-in-Hand counter-ledger on a bank statement means a self
    # transfer (this was a cash deposit), so the generated voucher should be Contra.
    voucher = VoucherRepository(db_session).get_by_transaction_id(transactions[0].id)
    contra_type = VoucherTypeRepository(db_session).get_by_name("Contra")
    assert voucher is not None
    assert voucher.voucher_type_id == contra_type.id
    assert voucher.voucher_number == "V00001"
    assert transactions[0].voucher_type_id == contra_type.id


def test_pipeline_stays_in_review_required_when_transaction_unresolved(db_session, tmp_path):
    # No rules/ledgers seeded, so the CASH_DEPOSIT-only row still won't resolve; AI
    # prediction is skipped here by never seeding a Gemini client, since the
    # unresolved set only contains rows the deterministic waterfall could handle -
    # we assert on the pre-AI state by calling validation directly after matching.
    csv_content = (
        "Date,Narration,Debit,Credit,Balance\n"
        "01-01-2026,RTGS DR-REF12345 -SAMPLE VENDOR LIMITED -HDFC0000021,50000,0,-40250.00\n"
    ).encode()
    uploaded_file = _create_uploaded_file(db_session, tmp_path, "statement.csv", csv_content, FileType.CSV)
    job = JobRepository(db_session).create(uploaded_file.id)

    process_job(db_session, claim_next_queued_job(db_session))
    normalize_job(db_session, claim_next_normalizing_job(db_session))
    apply_ledger_matching_job(db_session, claim_next_matching_job(db_session))

    # Skip actually running the AI stage (claiming alone advances AI_PREDICTING ->
    # VALIDATING) - the point of this test is validation behaviour on a row that's
    # still unresolved, not AI prediction itself.
    claim_next_ai_predicting_job(db_session)

    claimed = claim_next_validating_job(db_session)
    assert claimed is not None

    apply_validation_job(db_session, claimed)

    db_session.refresh(claimed)
    assert claimed.status == JobStatus.REVIEW_REQUIRED
    assert claimed.manual_review_count == 1
    assert claimed.export_ready_count == 0

    transactions = ParsedTransactionRepository(db_session).list_for_job(job.id)
    assert transactions[0].ledger_id is None


def test_process_job_marks_failed_on_unparsable_file(db_session, tmp_path):
    uploaded_file = _create_uploaded_file(
        db_session, tmp_path, "empty.csv", b"Foo,Bar\n1,2\n", FileType.CSV
    )
    job = JobRepository(db_session).create(uploaded_file.id)

    claimed = claim_next_queued_job(db_session)
    process_job(db_session, claimed)

    db_session.refresh(claimed)
    assert claimed.status == JobStatus.FAILED
    assert claimed.error_message is not None
