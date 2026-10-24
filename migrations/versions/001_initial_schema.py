"""Initial database schema: leads, conversations, messages, bookings, outbox, escalations, audits

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-24 06:47:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Leads table
    op.create_table(
        'leads',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('contact_name', sa.String(length=128), nullable=True),
        sa.Column('company_name', sa.String(length=128), nullable=True),
        sa.Column('budget', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=8), server_default='USD', nullable=False),
        sa.Column('company_size', sa.String(length=64), nullable=True),
        sa.Column('business_problem', sa.Text(), nullable=True),
        sa.Column('urgency', sa.String(length=16), server_default='MEDIUM', nullable=False),
        sa.Column('decision_maker', sa.String(length=16), server_default='UNKNOWN', nullable=False),
        sa.Column('purchase_timeline', sa.String(length=64), nullable=True),
        sa.Column('qualification_status', sa.String(length=32), server_default='NEW', nullable=False),
        sa.Column('qualification_score', sa.Float(), nullable=True),
        sa.Column('consent_given', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('external_crm_id', sa.String(length=128), nullable=True),
        sa.Column('crm_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_leads_phone_number', 'leads', ['phone_number'], unique=True)

    # Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('lead_id', sa.String(length=36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('current_state', sa.String(length=32), server_default='NEW', nullable=False),
        sa.Column('previous_state', sa.String(length=32), nullable=True),
        sa.Column('state_metadata', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversations_lead_id', 'conversations', ['lead_id'])
    op.create_index('ix_conversations_phone_number', 'conversations', ['phone_number'])
    op.create_index('ix_conversations_current_state', 'conversations', ['current_state'])

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('meta_message_id', sa.String(length=128), nullable=True),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('sender_id', sa.String(length=64), nullable=False),
        sa.Column('message_type', sa.String(length=32), server_default='TEXT', nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('ix_messages_meta_message_id', 'messages', ['meta_message_id'], unique=True)

    # Bookings table
    op.create_table(
        'bookings',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(length=36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(length=32), server_default='mock', nullable=False),
        sa.Column('external_event_id', sa.String(length=128), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='CONFIRMED', nullable=False),
        sa.Column('meeting_url', sa.String(length=256), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_bookings_conversation_id', 'bookings', ['conversation_id'])
    op.create_index('ix_bookings_lead_id', 'bookings', ['lead_id'])
    op.create_index('ix_bookings_external_event_id', 'bookings', ['external_event_id'])

    # Outbox Events table
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='5', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_outbox_events_event_type', 'outbox_events', ['event_type'])
    op.create_index('ix_outbox_events_status', 'outbox_events', ['status'])

    # Handoff Escalations table
    op.create_table(
        'handoff_escalations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('trigger_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='OPEN', nullable=False),
        sa.Column('assigned_agent', sa.String(length=128), nullable=True),
        sa.Column('dossier_summary', sa.JSON(), nullable=False),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_handoff_escalations_conversation_id', 'handoff_escalations', ['conversation_id'])
    op.create_index('ix_handoff_escalations_status', 'handoff_escalations', ['status'])

    # Audit Events table
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=32), nullable=False),
        sa.Column('resource_id', sa.String(length=64), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_events_correlation_id', 'audit_events', ['correlation_id'])
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('handoff_escalations')
    op.drop_table('outbox_events')
    op.drop_table('bookings')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('leads')
