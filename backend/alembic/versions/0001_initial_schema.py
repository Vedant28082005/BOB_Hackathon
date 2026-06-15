"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'applicant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('applicant_uuid', sa.String(), nullable=False),
        sa.Column('name_hash', sa.String(), nullable=False),
        sa.Column('email_hash', sa.String(), nullable=False),
        sa.Column('phone_hash', sa.String(), nullable=False),
        sa.Column('pan_hash', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('doc_type', sa.String(), nullable=False),
        sa.Column('dob', sa.String(), nullable=False),
        sa.Column('device_fingerprint', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=False),
        sa.Column('email_domain', sa.String(), nullable=False),
        sa.Column('phone_prefix', sa.String(), nullable=False),
        sa.Column('scenario', sa.String(), nullable=False, server_default='genuine_user'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_applicant_applicant_uuid', 'applicant', ['applicant_uuid'])
    op.create_index('ix_applicant_device_fingerprint', 'applicant', ['device_fingerprint'])
    op.create_index('ix_applicant_ip_address', 'applicant', ['ip_address'])
    op.create_index('ix_applicant_email_domain', 'applicant', ['email_domain'])
    op.create_index('ix_applicant_phone_prefix', 'applicant', ['phone_prefix'])

    op.create_table(
        'assessment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_uuid', sa.String(), nullable=False),
        sa.Column('applicant_uuid', sa.String(), nullable=False),
        sa.Column('applicant_id', sa.String(), nullable=True),
        sa.Column('document_score', sa.Float(), nullable=False),
        sa.Column('biometric_score', sa.Float(), nullable=False),
        sa.Column('device_score', sa.Float(), nullable=False),
        sa.Column('behavioural_score', sa.Float(), nullable=False),
        sa.Column('identity_graph_score', sa.Float(), nullable=False),
        sa.Column('trust_score', sa.Float(), nullable=False),
        sa.Column('risk_band', sa.String(), nullable=False),
        sa.Column('decision', sa.String(), nullable=False),
        sa.Column('reason_codes_json', sa.String(), nullable=False),
        sa.Column('signals_json', sa.String(), nullable=False),
        sa.Column('llm_explanation', sa.String(), nullable=False, server_default=''),
        sa.Column('processing_time_ms', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_assessment_assessment_uuid', 'assessment', ['assessment_uuid'])
    op.create_index('ix_assessment_applicant_uuid', 'assessment', ['applicant_uuid'])
    op.create_index('ix_assessment_applicant_id', 'assessment', ['applicant_id'])

    op.create_table(
        'auditentry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entry_uuid', sa.String(), nullable=False),
        sa.Column('assessment_uuid', sa.String(), nullable=True),
        sa.Column('applicant_uuid', sa.String(), nullable=True),
        sa.Column('applicant_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False, server_default=''),
        sa.Column('payload_json', sa.String(), nullable=False, server_default='{}'),
        sa.Column('payload', sa.String(), nullable=True),
        sa.Column('prev_hash', sa.String(), nullable=False),
        sa.Column('record_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auditentry_entry_uuid', 'auditentry', ['entry_uuid'])
    op.create_index('ix_auditentry_assessment_uuid', 'auditentry', ['assessment_uuid'])
    op.create_index('ix_auditentry_applicant_uuid', 'auditentry', ['applicant_uuid'])
    op.create_index('ix_auditentry_applicant_id', 'auditentry', ['applicant_id'])


def downgrade() -> None:
    op.drop_table('auditentry')
    op.drop_table('assessment')
    op.drop_table('applicant')
