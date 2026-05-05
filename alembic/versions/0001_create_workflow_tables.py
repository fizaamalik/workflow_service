"""create workflow tables

Revision ID: 0001
Revises:
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wf_workflow_definition",
        sa.Column("workflow_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("workflow_code", sa.String(100), nullable=False),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("entity_name", sa.String(150), nullable=False),
        sa.Column("entity_table_name", sa.String(150), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_action", sa.String(100), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("allow_parallel_approval", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("allow_delegation", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("allow_send_back", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("allow_reminder", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("org_id", "workflow_code", "version_no", name="uq_wf_code_version"),
    )

    op.create_table(
        "wf_node",
        sa.Column("node_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger, sa.ForeignKey("wf_workflow_definition.workflow_id"), nullable=False, index=True),
        sa.Column("org_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("node_code", sa.String(100), nullable=False),
        sa.Column("node_name", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("sequence_no", sa.Integer),
        sa.Column("is_start_node", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_end_node", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("assignment_type", sa.String(50)),
        sa.Column("assigned_user_id", sa.BigInteger),
        sa.Column("assigned_role_id", sa.BigInteger),
        sa.Column("dynamic_assignment_field", sa.String(150)),
        sa.Column("assignment_strategy", sa.String(50), nullable=False, server_default="FIRST_AVAILABLE"),
        sa.Column("maker_checker_required", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("allow_self_approval", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sla_hours", sa.Integer),
        sa.Column("escalation_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("escalation_after_hours", sa.Integer),
        sa.Column("escalation_to_role_id", sa.BigInteger),
        sa.UniqueConstraint("workflow_id", "node_code", name="uq_wf_node_code"),
    )

    op.create_table(
        "wf_node_action",
        sa.Column("node_action_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("node_id", sa.BigInteger, sa.ForeignKey("wf_node.node_id"), nullable=False, index=True),
        sa.Column("org_id", sa.BigInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("action_code", sa.String(100), nullable=False),
        sa.Column("action_name", sa.String(150), nullable=False),
        sa.Column("requires_comment", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("requires_attachment", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_positive_action", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_negative_action", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("node_id", "action_code", name="uq_node_action"),
    )

    op.create_table(
        "wf_transition",
        sa.Column("transition_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger, sa.ForeignKey("wf_workflow_definition.workflow_id"), nullable=False, index=True),
        sa.Column("from_node_id", sa.BigInteger, sa.ForeignKey("wf_node.node_id"), nullable=False),
        sa.Column("to_node_id", sa.BigInteger, sa.ForeignKey("wf_node.node_id"), nullable=False),
        sa.Column("org_id", sa.BigInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("action_code", sa.String(100), nullable=False),
        sa.Column("condition_expression", sa.Text),
        sa.Column("priority", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "wf_instance",
        sa.Column("workflow_instance_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger, sa.ForeignKey("wf_workflow_definition.workflow_id"), nullable=False, index=True),
        sa.Column("org_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("entity_name", sa.String(150), nullable=False),
        sa.Column("entity_table_name", sa.String(150), nullable=False),
        sa.Column("entity_record_id", sa.String(100), nullable=False),
        sa.Column("current_node_id", sa.BigInteger, sa.ForeignKey("wf_node.node_id"), index=True),
        sa.Column("workflow_status", sa.String(50), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("initiated_by", sa.BigInteger, nullable=False),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by", sa.BigInteger),
        sa.Column("last_action_code", sa.String(100)),
        sa.Column("last_action_by", sa.BigInteger),
        sa.Column("last_action_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.JSON),
        sa.UniqueConstraint("workflow_id", "entity_name", "entity_record_id", name="uq_workflow_entity_record"),
    )

    op.create_table(
        "wf_task",
        sa.Column("workflow_task_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_instance_id", sa.BigInteger, sa.ForeignKey("wf_instance.workflow_instance_id"), nullable=False, index=True),
        sa.Column("workflow_id", sa.BigInteger, sa.ForeignKey("wf_workflow_definition.workflow_id"), nullable=False),
        sa.Column("node_id", sa.BigInteger, sa.ForeignKey("wf_node.node_id"), nullable=False),
        sa.Column("org_id", sa.BigInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("task_status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("assigned_to_user_id", sa.BigInteger, index=True),
        sa.Column("assigned_to_role_id", sa.BigInteger),
        sa.Column("assignment_type", sa.String(50)),
        sa.Column("assignment_strategy", sa.String(50)),
        sa.Column("claimed_by", sa.BigInteger),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("action_taken", sa.String(100)),
        sa.Column("action_taken_by", sa.BigInteger),
        sa.Column("action_taken_at", sa.DateTime(timezone=True)),
        sa.Column("comments", sa.Text),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("reminder_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "wf_task_candidate_user",
        sa.Column("task_candidate_user_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_task_id", sa.BigInteger, sa.ForeignKey("wf_task.workflow_task_id"), nullable=False, index=True),
        sa.Column("user_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("org_id", sa.BigInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("workflow_task_id", "user_id", name="uq_task_candidate_user"),
    )

    op.create_table(
        "wf_action_history",
        sa.Column("workflow_action_history_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_instance_id", sa.BigInteger, sa.ForeignKey("wf_instance.workflow_instance_id"), nullable=False, index=True),
        sa.Column("workflow_task_id", sa.BigInteger, sa.ForeignKey("wf_task.workflow_task_id")),
        sa.Column("org_id", sa.BigInteger, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("from_node_id", sa.BigInteger),
        sa.Column("to_node_id", sa.BigInteger),
        sa.Column("action_code", sa.String(100), nullable=False),
        sa.Column("action_by", sa.BigInteger, nullable=False),
        sa.Column("action_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comments", sa.Text),
        sa.Column("action_payload", sa.JSON),
        sa.Column("ip_address", sa.String(100)),
        sa.Column("user_agent", sa.Text),
    )

    op.create_table(
        "wf_reminder",
        sa.Column("workflow_reminder_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("workflow_instance_id", sa.BigInteger, sa.ForeignKey("wf_instance.workflow_instance_id"), nullable=False, index=True),
        sa.Column("workflow_task_id", sa.BigInteger, sa.ForeignKey("wf_task.workflow_task_id"), nullable=False),
        sa.Column("org_id", sa.BigInteger, nullable=False),
        sa.Column("reminder_sent_by", sa.BigInteger, nullable=False),
        sa.Column("reminder_sent_to", sa.BigInteger, nullable=False),
        sa.Column("reminder_message", sa.Text),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notification_status", sa.String(50)),
    )


def downgrade():
    op.drop_table("wf_reminder")
    op.drop_table("wf_action_history")
    op.drop_table("wf_task_candidate_user")
    op.drop_table("wf_task")
    op.drop_table("wf_instance")
    op.drop_table("wf_transition")
    op.drop_table("wf_node_action")
    op.drop_table("wf_node")
    op.drop_table("wf_workflow_definition")