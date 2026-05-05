from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_definition import WorkflowDefinition
from app.models.workflow_node import WorkflowNode
from app.models.workflow_action import WorkflowAction
from app.models.workflow_transition import WorkflowTransition
from app.core.exceptions import BusinessException


class WorkflowDefinitionService:
    """
    Manages the lifecycle of workflow definitions:
    create → add nodes → add actions → add transitions → publish.
    Publishing is a one-way operation; changes require a new version.
    """

    # ── Workflow ─────────────────────────────────────────────────────────────

    async def create_workflow(
        self, db: AsyncSession, request, current_user: dict
    ) -> dict:
        exists = (
            await db.execute(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.org_id == current_user["org_id"],
                    WorkflowDefinition.workflow_code == request.workflow_code,
                    WorkflowDefinition.version_no == request.version_no,
                    WorkflowDefinition.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(
                status_code=409,
                detail=f"Workflow '{request.workflow_code}' version {request.version_no} already exists",
            )

        wf = WorkflowDefinition(
            org_id=current_user["org_id"],
            workflow_code=request.workflow_code,
            workflow_name=request.workflow_name,
            description=request.description,
            entity_name=request.entity_name,
            entity_table_name=request.entity_table_name,
            trigger_type=request.trigger_type,
            trigger_action=request.trigger_action,
            version_no=request.version_no,
            is_published=False,
            created_by=current_user["user_id"],
            created_at=datetime.now(timezone.utc),
            is_active=True,
            is_deleted=False,
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        return {"workflow_id": wf.workflow_id, "message": "Workflow definition created"}

    async def get_workflow(
        self, db: AsyncSession, workflow_id: int, current_user: dict
    ) -> WorkflowDefinition:
        wf = await self._get_wf_or_404(db, workflow_id, current_user)
        return wf

    async def list_workflows(
        self, db: AsyncSession, current_user: dict
    ) -> list[WorkflowDefinition]:
        rows = (
            await db.execute(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.org_id == current_user["org_id"],
                    WorkflowDefinition.is_deleted == False,
                ).order_by(WorkflowDefinition.workflow_code, WorkflowDefinition.version_no)
            )
        ).scalars().all()
        return list(rows)

    async def update_workflow(
        self, db: AsyncSession, workflow_id: int, request, current_user: dict
    ) -> dict:
        wf = await self._get_wf_or_404(db, workflow_id, current_user)
        if wf.is_published:
            raise BusinessException(
                "Cannot edit a published workflow. Create a new version instead.",
                code="WORKFLOW_PUBLISHED",
            )
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(wf, field, value)
        wf.updated_by = current_user["user_id"]
        wf.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"message": "Workflow updated"}

    async def publish_workflow(
        self, db: AsyncSession, workflow_id: int, current_user: dict
    ) -> dict:
        wf = await self._get_wf_or_404(db, workflow_id, current_user)
        if wf.is_published:
            raise BusinessException("Workflow is already published", code="ALREADY_PUBLISHED")

        # Exactly one START node
        start_count = (
            await db.execute(
                select(func.count()).select_from(WorkflowNode).where(
                    WorkflowNode.workflow_id == workflow_id,
                    WorkflowNode.is_start_node == True,
                    WorkflowNode.is_deleted == False,
                )
            )
        ).scalar_one()
        if start_count != 1:
            raise BusinessException(
                f"Workflow must have exactly one start node (found {start_count})",
                code="INVALID_WORKFLOW_STRUCTURE",
            )

        # At least one END node
        end_count = (
            await db.execute(
                select(func.count()).select_from(WorkflowNode).where(
                    WorkflowNode.workflow_id == workflow_id,
                    WorkflowNode.is_end_node == True,
                    WorkflowNode.is_deleted == False,
                )
            )
        ).scalar_one()
        if end_count < 1:
            raise BusinessException(
                "Workflow must have at least one end node",
                code="INVALID_WORKFLOW_STRUCTURE",
            )

        # At least one transition from start node
        start_node = (
            await db.execute(
                select(WorkflowNode).where(
                    WorkflowNode.workflow_id == workflow_id,
                    WorkflowNode.is_start_node == True,
                    WorkflowNode.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if start_node:
            transition_count = (
                await db.execute(
                    select(func.count()).select_from(WorkflowTransition).where(
                        WorkflowTransition.workflow_id == workflow_id,
                        WorkflowTransition.from_node_id == start_node.node_id,
                        WorkflowTransition.is_active == True,
                        WorkflowTransition.is_deleted == False,
                    )
                )
            ).scalar_one()
            if transition_count == 0:
                raise BusinessException(
                    "Start node must have at least one outgoing transition",
                    code="INVALID_WORKFLOW_STRUCTURE",
                )

        wf.is_published = True
        wf.updated_by = current_user["user_id"]
        wf.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"message": "Workflow published successfully"}

    # ── Nodes ─────────────────────────────────────────────────────────────────

    async def add_node(
        self, db: AsyncSession, workflow_id: int, request, current_user: dict
    ) -> dict:
        wf = await self._get_wf_or_404(db, workflow_id, current_user)
        if wf.is_published:
            raise BusinessException(
                "Cannot add nodes to a published workflow", code="WORKFLOW_PUBLISHED"
            )

        # Enforce single start node per workflow
        if request.is_start_node:
            existing_start = (
                await db.execute(
                    select(func.count()).select_from(WorkflowNode).where(
                        WorkflowNode.workflow_id == workflow_id,
                        WorkflowNode.is_start_node == True,
                        WorkflowNode.is_deleted == False,
                    )
                )
            ).scalar_one()
            if existing_start > 0:
                raise BusinessException(
                    "A start node already exists for this workflow",
                    code="DUPLICATE_START_NODE",
                )

        node = WorkflowNode(
            org_id=current_user["org_id"],
            workflow_id=workflow_id,
            node_code=request.node_code,
            node_name=request.node_name,
            node_type=request.node_type,
            sequence_no=request.sequence_no,
            is_start_node=request.is_start_node,
            is_end_node=request.is_end_node,
            assignment_type=request.assignment_type,
            assigned_user_id=request.assigned_user_id,
            assigned_role_id=request.assigned_role_id,
            dynamic_assignment_field=request.dynamic_assignment_field,
            assignment_strategy=request.assignment_strategy,
            maker_checker_required=request.maker_checker_required,
            allow_self_approval=request.allow_self_approval,
            sla_hours=request.sla_hours,
            escalation_enabled=request.escalation_enabled,
            escalation_after_hours=request.escalation_after_hours,
            escalation_to_role_id=request.escalation_to_role_id,
            created_by=current_user["user_id"],
            created_at=datetime.now(timezone.utc),
            is_active=True,
            is_deleted=False,
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return {"node_id": node.node_id, "message": "Node added"}

    async def list_nodes(
        self, db: AsyncSession, workflow_id: int, current_user: dict
    ) -> list[WorkflowNode]:
        await self._get_wf_or_404(db, workflow_id, current_user)
        rows = (
            await db.execute(
                select(WorkflowNode).where(
                    WorkflowNode.workflow_id == workflow_id,
                    WorkflowNode.is_deleted == False,
                ).order_by(WorkflowNode.sequence_no.asc().nullslast())
            )
        ).scalars().all()
        return list(rows)

    async def delete_node(
        self, db: AsyncSession, node_id: int, current_user: dict
    ) -> dict:
        node = await self._get_node_or_404(db, node_id, current_user)
        wf = await db.get(WorkflowDefinition, node.workflow_id)
        if wf and wf.is_published:
            raise BusinessException(
                "Cannot delete nodes from a published workflow", code="WORKFLOW_PUBLISHED"
            )
        node.is_deleted = True
        node.is_active = False
        node.updated_by = current_user["user_id"]
        node.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"message": "Node deleted"}

    # ── Actions ───────────────────────────────────────────────────────────────

    async def add_action(
        self, db: AsyncSession, node_id: int, request, current_user: dict
    ) -> dict:
        node = await self._get_node_or_404(db, node_id, current_user)
        wf = await db.get(WorkflowDefinition, node.workflow_id)
        if wf and wf.is_published:
            raise BusinessException(
                "Cannot add actions to a node in a published workflow",
                code="WORKFLOW_PUBLISHED",
            )

        action = WorkflowAction(
            org_id=current_user["org_id"],
            node_id=node_id,
            action_code=request.action_code,
            action_name=request.action_name,
            requires_comment=request.requires_comment,
            requires_attachment=request.requires_attachment,
            is_positive_action=request.is_positive_action,
            is_negative_action=request.is_negative_action,
            display_order=request.display_order,
            created_by=current_user["user_id"],
            created_at=datetime.now(timezone.utc),
            is_active=True,
            is_deleted=False,
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)
        return {"node_action_id": action.node_action_id, "message": "Action added"}

    async def list_actions(
        self, db: AsyncSession, node_id: int, current_user: dict
    ) -> list[WorkflowAction]:
        await self._get_node_or_404(db, node_id, current_user)
        rows = (
            await db.execute(
                select(WorkflowAction).where(
                    WorkflowAction.node_id == node_id,
                    WorkflowAction.is_deleted == False,
                ).order_by(WorkflowAction.display_order)
            )
        ).scalars().all()
        return list(rows)

    # ── Transitions ───────────────────────────────────────────────────────────

    async def add_transition(
        self, db: AsyncSession, workflow_id: int, request, current_user: dict
    ) -> dict:
        wf = await self._get_wf_or_404(db, workflow_id, current_user)
        if wf.is_published:
            raise BusinessException(
                "Cannot add transitions to a published workflow", code="WORKFLOW_PUBLISHED"
            )

        # Validate that from_node and to_node belong to this workflow
        from_node = await db.get(WorkflowNode, request.from_node_id)
        if not from_node or from_node.workflow_id != workflow_id or from_node.is_deleted:
            raise HTTPException(status_code=400, detail="from_node_id does not belong to this workflow")
        to_node = await db.get(WorkflowNode, request.to_node_id)
        if not to_node or to_node.workflow_id != workflow_id or to_node.is_deleted:
            raise HTTPException(status_code=400, detail="to_node_id does not belong to this workflow")

        # Cannot transition FROM an end node
        if from_node.is_end_node:
            raise BusinessException(
                "Cannot add transitions from an end node", code="INVALID_TRANSITION"
            )

        transition = WorkflowTransition(
            org_id=current_user["org_id"],
            workflow_id=workflow_id,
            from_node_id=request.from_node_id,
            action_code=request.action_code,
            to_node_id=request.to_node_id,
            condition_expression=request.condition_expression,
            priority=request.priority,
            is_default=request.is_default,
            created_by=current_user["user_id"],
            created_at=datetime.now(timezone.utc),
            is_active=True,
            is_deleted=False,
        )
        db.add(transition)
        await db.commit()
        await db.refresh(transition)
        return {"transition_id": transition.transition_id, "message": "Transition added"}

    async def list_transitions(
        self, db: AsyncSession, workflow_id: int, current_user: dict
    ) -> list[WorkflowTransition]:
        await self._get_wf_or_404(db, workflow_id, current_user)
        rows = (
            await db.execute(
                select(WorkflowTransition).where(
                    WorkflowTransition.workflow_id == workflow_id,
                    WorkflowTransition.is_deleted == False,
                ).order_by(WorkflowTransition.from_node_id, WorkflowTransition.priority)
            )
        ).scalars().all()
        return list(rows)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_wf_or_404(
        self, db: AsyncSession, workflow_id: int, current_user: dict
    ) -> WorkflowDefinition:
        wf = await db.get(WorkflowDefinition, workflow_id)
        if not wf or wf.org_id != current_user["org_id"] or wf.is_deleted:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return wf

    async def _get_node_or_404(
        self, db: AsyncSession, node_id: int, current_user: dict
    ) -> WorkflowNode:
        node = await db.get(WorkflowNode, node_id)
        if not node or node.org_id != current_user["org_id"] or node.is_deleted:
            raise HTTPException(status_code=404, detail="Node not found")
        return node