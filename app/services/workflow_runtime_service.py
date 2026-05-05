from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_definition import WorkflowDefinition
from app.models.workflow_node import WorkflowNode
from app.models.workflow_action import WorkflowAction
from app.models.workflow_transition import WorkflowTransition
from app.models.workflow_instance import WorkflowInstance
from app.models.workflow_task import WorkflowTask
from app.models.workflow_task_candidate import WorkflowTaskCandidate
from app.models.workflow_history import WorkflowHistory
from app.models.workflow_reminder import WorkflowReminder

from app.services.assignee_service import AssigneeService
from app.services.maker_checker_service import MakerCheckerService
from app.clients.entity_service_client import EntityServiceClient
from app.clients.notification_client import NotificationClient
from app.core.exceptions import BusinessException


class WorkflowRuntimeService:
    """
    Core workflow execution engine.

    Key flows:
      start_workflow   – find active workflow → validate → create instance + first task
      perform_action   – validate actor → apply action → transition → create next task or close
      claim_task       – for ROLE/ALL_USERS pools, claim a task to indicate ownership
      send_reminder    – initiator sends reminder to current task assignees
      get_pending_tasks – list tasks visible to the current user
      get_task_detail   – full task detail with allowed actions
      get_instance      – full instance detail with history
    """

    _assignee_svc = AssigneeService()
    _entity_client = EntityServiceClient()
    _notif_client = NotificationClient()

    # ── Start ─────────────────────────────────────────────────────────────────

    async def start_workflow(
        self,
        db: AsyncSession,
        request,
        current_user: dict,
        auth_header: str,
        meta: dict | None = None,
    ) -> dict:
        # 1. Find the active, published workflow for this entity + trigger_action
        wf_row = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.org_id == current_user["org_id"],
                WorkflowDefinition.entity_name == request.entity_name,
                WorkflowDefinition.entity_table_name == request.entity_table_name,
                WorkflowDefinition.trigger_action == request.trigger_action
                if hasattr(request, "trigger_action")
                else WorkflowDefinition.trigger_action == "SUBMIT",
                WorkflowDefinition.is_published == True,
                WorkflowDefinition.is_deleted == False,
                WorkflowDefinition.is_active == True,
            ).order_by(WorkflowDefinition.version_no.desc())
        )
        workflow = wf_row.scalars().first()
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No active published workflow found for entity='{request.entity_name}' "
                    f"table='{request.entity_table_name}'"
                ),
            )

        # 2. Prevent duplicate instances
        existing = (
            await db.execute(
                select(WorkflowInstance).where(
                    WorkflowInstance.org_id == current_user["org_id"],
                    WorkflowInstance.workflow_id == workflow.workflow_id,
                    WorkflowInstance.entity_name == request.entity_name,
                    WorkflowInstance.entity_record_id == request.entity_record_id,
                    WorkflowInstance.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise BusinessException(
                f"Workflow already started for entity_record_id='{request.entity_record_id}'",
                code="WORKFLOW_ALREADY_STARTED",
                status_code=409,
            )

        # 3. Locate START node
        start_node = (
            await db.execute(
                select(WorkflowNode).where(
                    WorkflowNode.workflow_id == workflow.workflow_id,
                    WorkflowNode.is_start_node == True,
                    WorkflowNode.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if not start_node:
            raise BusinessException(
                "Workflow configuration error: no start node found",
                code="WORKFLOW_CONFIG_ERROR",
                status_code=500,
            )

        # 4. Get transition from START → first real node
        transition = (
            await db.execute(
                select(WorkflowTransition).where(
                    WorkflowTransition.workflow_id == workflow.workflow_id,
                    WorkflowTransition.from_node_id == start_node.node_id,
                    WorkflowTransition.is_active == True,
                    WorkflowTransition.is_deleted == False,
                ).order_by(WorkflowTransition.priority.asc())
            )
        ).scalars().first()
        if not transition:
            raise BusinessException(
                "Workflow configuration error: no transition from start node",
                code="WORKFLOW_CONFIG_ERROR",
                status_code=500,
            )

        next_node = await db.get(WorkflowNode, transition.to_node_id)
        if not next_node:
            raise BusinessException(
                "Workflow configuration error: target node not found",
                code="WORKFLOW_CONFIG_ERROR",
                status_code=500,
            )

        # 5. Resolve assignees + maker-checker check
        assignees = await self._assignee_svc.resolve_assignees(
            db, next_node, request.payload, auth_header
        )
        MakerCheckerService.validate_start(
            initiated_by=current_user["user_id"],
            assignees=assignees,
            allow_self_approval=next_node.allow_self_approval,
        )

        # 6. Persist: instance + task + candidates + history
        now = datetime.now(timezone.utc)

        instance = WorkflowInstance(
            org_id=current_user["org_id"],
            workflow_id=workflow.workflow_id,
            entity_name=request.entity_name,
            entity_table_name=request.entity_table_name,
            entity_record_id=request.entity_record_id,
            current_node_id=next_node.node_id,
            workflow_status="IN_PROGRESS",
            initiated_by=current_user["user_id"],
            initiated_at=now,
            metadata_json=request.payload,
            created_by=current_user["user_id"],
            created_at=now,
            is_active=True,
            is_deleted=False,
        )
        db.add(instance)
        await db.flush()

        task = await self._create_task(
            db=db,
            instance=instance,
            node=next_node,
            assignees=assignees,
            current_user=current_user,
            now=now,
        )

        db.add(
            WorkflowHistory(
                org_id=current_user["org_id"],
                workflow_instance_id=instance.workflow_instance_id,
                workflow_task_id=task.workflow_task_id,
                from_node_id=start_node.node_id,
                to_node_id=next_node.node_id,
                action_code="SUBMIT",
                action_by=current_user["user_id"],
                action_at=now,
                action_payload=request.payload,
                ip_address=(meta or {}).get("ip_address"),
                user_agent=(meta or {}).get("user_agent"),
                created_by=current_user["user_id"],
                created_at=now,
                is_active=True,
                is_deleted=False,
            )
        )
        await db.commit()

        # 7. Notify entity service (best-effort)
        await self._entity_client.update_workflow_status(
            entity_name=request.entity_name,
            entity_record_id=request.entity_record_id,
            payload={
                "workflow_instance_id": instance.workflow_instance_id,
                "workflow_status": "IN_PROGRESS",
                "current_workflow_node": next_node.node_name,
                "last_action": "SUBMIT",
                "last_action_by": current_user["user_id"],
            },
            auth_header=auth_header,
        )

        # 8. Notify assignees
        await self._notif_client.send({
            "type": "WORKFLOW_TASK_ASSIGNED",
            "workflow_instance_id": instance.workflow_instance_id,
            "workflow_task_id": task.workflow_task_id,
            "node_name": next_node.node_name,
            "entity_name": request.entity_name,
            "entity_record_id": request.entity_record_id,
            "recipients": assignees,
        })

        return {
            "workflow_instance_id": instance.workflow_instance_id,
            "workflow_status": "IN_PROGRESS",
            "current_node": next_node.node_name,
            "task_id": task.workflow_task_id,
            "assigned_to_user_ids": assignees,
        }

    # ── Perform action ────────────────────────────────────────────────────────

    async def perform_action(
        self,
        db: AsyncSession,
        task_id: int,
        request,
        current_user: dict,
        auth_header: str,
        meta: dict | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)

        # 1. Load task with row-level lock
        task = (
            await db.execute(
                select(WorkflowTask).where(
                    WorkflowTask.workflow_task_id == task_id,
                    WorkflowTask.org_id == current_user["org_id"],
                    WorkflowTask.is_deleted == False,
                ).with_for_update()
            )
        ).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.task_status not in ("PENDING", "CLAIMED"):
            raise BusinessException(
                f"Task is already '{task.task_status}' and cannot accept actions",
                code="TASK_NOT_ACTIONABLE",
                status_code=409,
            )

        # 2. Load instance + node
        instance = await db.get(WorkflowInstance, task.workflow_instance_id)
        if not instance or instance.org_id != current_user["org_id"]:
            raise HTTPException(status_code=404, detail="Workflow instance not found")
        if instance.workflow_status != "IN_PROGRESS":
            raise BusinessException(
                "Workflow instance is no longer in progress",
                code="WORKFLOW_NOT_IN_PROGRESS",
                status_code=409,
            )

        current_node = await db.get(WorkflowNode, task.node_id)
        if not current_node:
            raise HTTPException(status_code=404, detail="Node not found")

        # 3. Maker-checker + assignment check
        assignees = await self._get_task_assignees(db, task)
        MakerCheckerService.validate_action(
            actor_user_id=current_user["user_id"],
            initiated_by=instance.initiated_by,
            assignees=assignees,
            allow_self_approval=current_node.allow_self_approval,
        )

        # 4. Check action is allowed on this node
        allowed_action = (
            await db.execute(
                select(WorkflowAction).where(
                    WorkflowAction.node_id == current_node.node_id,
                    WorkflowAction.action_code == request.action_code,
                    WorkflowAction.is_deleted == False,
                    WorkflowAction.is_active == True,
                )
            )
        ).scalar_one_or_none()
        if not allowed_action:
            raise BusinessException(
                f"Action '{request.action_code}' is not allowed on node '{current_node.node_name}'",
                code="ACTION_NOT_ALLOWED",
                status_code=400,
            )

        # 5. Validate comment / attachment requirements
        if allowed_action.requires_comment and not (request.comments or "").strip():
            raise BusinessException(
                f"A comment is required for action '{request.action_code}'",
                code="COMMENT_REQUIRED",
                status_code=422,
            )

        # 6. Resolve transition
        transition = await self._resolve_transition(
            db, instance, current_node, request.action_code, request.payload
        )
        next_node = await db.get(WorkflowNode, transition.to_node_id)
        if not next_node:
            raise BusinessException(
                "Workflow configuration error: next node not found",
                code="WORKFLOW_CONFIG_ERROR",
                status_code=500,
            )

        # 7. Complete current task
        task.task_status = "COMPLETED"
        task.action_taken = request.action_code
        task.action_taken_by = current_user["user_id"]
        task.action_taken_at = now
        task.comments = request.comments
        task.updated_by = current_user["user_id"]
        task.updated_at = now

        db.add(
            WorkflowHistory(
                org_id=current_user["org_id"],
                workflow_instance_id=instance.workflow_instance_id,
                workflow_task_id=task.workflow_task_id,
                from_node_id=current_node.node_id,
                to_node_id=next_node.node_id,
                action_code=request.action_code,
                action_by=current_user["user_id"],
                action_at=now,
                comments=request.comments,
                action_payload=request.payload,
                ip_address=(meta or {}).get("ip_address"),
                user_agent=(meta or {}).get("user_agent"),
                created_by=current_user["user_id"],
                created_at=now,
                is_active=True,
                is_deleted=False,
            )
        )

        # 8a. Terminal node → close instance
        if next_node.is_end_node:
            final_status = self._map_end_status(next_node.node_type)
            instance.current_node_id = next_node.node_id
            instance.workflow_status = final_status
            instance.completed_at = now
            instance.completed_by = current_user["user_id"]
            instance.last_action_code = request.action_code
            instance.last_action_by = current_user["user_id"]
            instance.last_action_at = now
            instance.updated_by = current_user["user_id"]
            instance.updated_at = now
            await db.commit()

            await self._entity_client.update_workflow_status(
                entity_name=instance.entity_name,
                entity_record_id=instance.entity_record_id,
                payload={
                    "workflow_instance_id": instance.workflow_instance_id,
                    "workflow_status": final_status,
                    "current_workflow_node": next_node.node_name,
                    "last_action": request.action_code,
                    "last_action_by": current_user["user_id"],
                },
                auth_header=auth_header,
            )
            return {
                "workflow_completed": True,
                "workflow_status": final_status,
                "next_task_id": None,
                "current_node": next_node.node_name,
            }

        # 8b. Non-terminal → resolve next assignees + create new task
        next_assignees = await self._assignee_svc.resolve_assignees(
            db, next_node, request.payload, auth_header
        )
        MakerCheckerService.validate_start(
            initiated_by=instance.initiated_by,
            assignees=next_assignees,
            allow_self_approval=next_node.allow_self_approval,
        )

        new_task = await self._create_task(
            db=db,
            instance=instance,
            node=next_node,
            assignees=next_assignees,
            current_user=current_user,
            now=now,
        )

        instance.current_node_id = next_node.node_id
        instance.last_action_code = request.action_code
        instance.last_action_by = current_user["user_id"]
        instance.last_action_at = now
        instance.updated_by = current_user["user_id"]
        instance.updated_at = now
        await db.commit()

        await self._entity_client.update_workflow_status(
            entity_name=instance.entity_name,
            entity_record_id=instance.entity_record_id,
            payload={
                "workflow_instance_id": instance.workflow_instance_id,
                "workflow_status": "IN_PROGRESS",
                "current_workflow_node": next_node.node_name,
                "last_action": request.action_code,
                "last_action_by": current_user["user_id"],
            },
            auth_header=auth_header,
        )

        await self._notif_client.send({
            "type": "WORKFLOW_TASK_ASSIGNED",
            "workflow_instance_id": instance.workflow_instance_id,
            "workflow_task_id": new_task.workflow_task_id,
            "node_name": next_node.node_name,
            "entity_name": instance.entity_name,
            "entity_record_id": instance.entity_record_id,
            "recipients": next_assignees,
        })

        return {
            "workflow_completed": False,
            "workflow_status": instance.workflow_status,
            "next_task_id": new_task.workflow_task_id,
            "current_node": next_node.node_name,
            "assigned_to_user_ids": next_assignees,
        }

    # ── Claim ─────────────────────────────────────────────────────────────────

    async def claim_task(
        self, db: AsyncSession, task_id: int, current_user: dict
    ) -> dict:
        task = (
            await db.execute(
                select(WorkflowTask).where(
                    WorkflowTask.workflow_task_id == task_id,
                    WorkflowTask.org_id == current_user["org_id"],
                    WorkflowTask.is_deleted == False,
                ).with_for_update()
            )
        ).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.task_status != "PENDING":
            raise BusinessException(
                f"Task cannot be claimed in status '{task.task_status}'",
                code="TASK_NOT_CLAIMABLE",
                status_code=400,
            )

        # Caller must be a candidate
        assignees = await self._get_task_assignees(db, task)
        if current_user["user_id"] not in assignees:
            raise BusinessException(
                "You are not eligible to claim this task",
                code="NOT_TASK_ASSIGNEE",
                status_code=403,
            )

        now = datetime.now(timezone.utc)
        task.claimed_by = current_user["user_id"]
        task.claimed_at = now
        task.task_status = "CLAIMED"
        task.updated_by = current_user["user_id"]
        task.updated_at = now
        await db.commit()
        return {
            "message": "Task claimed successfully",
            "task_id": task_id,
            "claimed_by": current_user["user_id"],
        }

    # ── Pending tasks ─────────────────────────────────────────────────────────

    async def get_pending_tasks(
        self, db: AsyncSession, current_user: dict
    ) -> list[dict]:
        stmt = (
            select(WorkflowTask, WorkflowInstance, WorkflowNode)
            .join(
                WorkflowInstance,
                WorkflowInstance.workflow_instance_id == WorkflowTask.workflow_instance_id,
            )
            .join(WorkflowNode, WorkflowNode.node_id == WorkflowTask.node_id)
            .where(
                WorkflowTask.org_id == current_user["org_id"],
                WorkflowTask.is_deleted == False,
                WorkflowTask.task_status.in_(["PENDING", "CLAIMED"]),
                (
                    (WorkflowTask.assigned_to_user_id == current_user["user_id"])
                    | (
                        WorkflowTask.workflow_task_id.in_(
                            select(WorkflowTaskCandidate.workflow_task_id).where(
                                WorkflowTaskCandidate.user_id == current_user["user_id"],
                                WorkflowTaskCandidate.is_deleted == False,
                            )
                        )
                    )
                ),
            )
            .order_by(WorkflowTask.due_at.asc().nullslast(), WorkflowTask.created_at.asc())
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                "workflow_task_id": task.workflow_task_id,
                "workflow_instance_id": inst.workflow_instance_id,
                "entity_name": inst.entity_name,
                "entity_record_id": inst.entity_record_id,
                "node_name": node.node_name,
                "task_status": task.task_status,
                "due_at": task.due_at.isoformat() if task.due_at else None,
                "assigned_to_user_id": task.assigned_to_user_id,
                "reminder_count": task.reminder_count,
            }
            for task, inst, node in rows
        ]

    # ── Task detail ───────────────────────────────────────────────────────────

    async def get_task_detail(
        self, db: AsyncSession, task_id: int, current_user: dict
    ) -> dict:
        task = await db.get(WorkflowTask, task_id)
        if not task or task.org_id != current_user["org_id"] or task.is_deleted:
            raise HTTPException(status_code=404, detail="Task not found")

        instance = await db.get(WorkflowInstance, task.workflow_instance_id)
        node = await db.get(WorkflowNode, task.node_id)

        # Allowed actions for this node
        actions = (
            await db.execute(
                select(WorkflowAction).where(
                    WorkflowAction.node_id == task.node_id,
                    WorkflowAction.is_deleted == False,
                    WorkflowAction.is_active == True,
                ).order_by(WorkflowAction.display_order)
            )
        ).scalars().all()

        return {
            "workflow_task_id": task.workflow_task_id,
            "workflow_instance_id": instance.workflow_instance_id if instance else None,
            "workflow_id": task.workflow_id,
            "node_id": task.node_id,
            "node_name": node.node_name if node else None,
            "node_type": node.node_type if node else None,
            "entity_name": instance.entity_name if instance else None,
            "entity_record_id": instance.entity_record_id if instance else None,
            "task_status": task.task_status,
            "assignment_type": task.assignment_type,
            "assigned_to_user_id": task.assigned_to_user_id,
            "claimed_by": task.claimed_by,
            "claimed_at": task.claimed_at.isoformat() if task.claimed_at else None,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "reminder_count": task.reminder_count,
            "allowed_actions": [
                {
                    "action_code": a.action_code,
                    "action_name": a.action_name,
                    "requires_comment": a.requires_comment,
                    "requires_attachment": a.requires_attachment,
                    "is_positive_action": a.is_positive_action,
                    "is_negative_action": a.is_negative_action,
                    "display_order": a.display_order,
                }
                for a in actions
            ],
            "initiated_by": instance.initiated_by if instance else None,
            "initiated_at": instance.initiated_at.isoformat() if instance else None,
        }

    # ── Instance detail with history ──────────────────────────────────────────

    async def get_instance_detail(
        self, db: AsyncSession, instance_id: int, current_user: dict
    ) -> dict:
        instance = await db.get(WorkflowInstance, instance_id)
        if not instance or instance.org_id != current_user["org_id"] or instance.is_deleted:
            raise HTTPException(status_code=404, detail="Workflow instance not found")

        current_node = (
            await db.get(WorkflowNode, instance.current_node_id)
            if instance.current_node_id
            else None
        )

        history_rows = (
            await db.execute(
                select(WorkflowHistory).where(
                    WorkflowHistory.workflow_instance_id == instance_id,
                    WorkflowHistory.is_deleted == False,
                ).order_by(WorkflowHistory.action_at.asc())
            )
        ).scalars().all()

        return {
            "workflow_instance_id": instance.workflow_instance_id,
            "workflow_id": instance.workflow_id,
            "entity_name": instance.entity_name,
            "entity_record_id": instance.entity_record_id,
            "workflow_status": instance.workflow_status,
            "current_node": current_node.node_name if current_node else None,
            "initiated_by": instance.initiated_by,
            "initiated_at": instance.initiated_at.isoformat(),
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
            "history": [
                {
                    "action_code": h.action_code,
                    "action_by": h.action_by,
                    "action_at": h.action_at.isoformat(),
                    "from_node_id": h.from_node_id,
                    "to_node_id": h.to_node_id,
                    "comments": h.comments,
                }
                for h in history_rows
            ],
        }

    # ── Reminder ──────────────────────────────────────────────────────────────

    async def send_reminder(
        self,
        db: AsyncSession,
        task_id: int,
        reminder_message: str,
        current_user: dict,
    ) -> dict:
        task = await db.get(WorkflowTask, task_id)
        if not task or task.org_id != current_user["org_id"] or task.is_deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.task_status != "PENDING":
            raise BusinessException(
                "Reminders can only be sent for PENDING tasks",
                code="REMINDER_NOT_ALLOWED",
                status_code=400,
            )

        instance = await db.get(WorkflowInstance, task.workflow_instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Workflow instance not found")

        # Only the workflow initiator can send reminders
        if instance.initiated_by != current_user["user_id"]:
            raise BusinessException(
                "Only the workflow initiator can send reminders",
                code="NOT_WORKFLOW_INITIATOR",
                status_code=403,
            )

        wf = await db.get(WorkflowDefinition, instance.workflow_id)
        if wf and not wf.allow_reminder:
            raise BusinessException(
                "Reminders are disabled for this workflow",
                code="REMINDER_DISABLED",
                status_code=400,
            )

        recipients = await self._get_task_assignees(db, task)
        now = datetime.now(timezone.utc)

        for user_id in recipients:
            db.add(
                WorkflowReminder(
                    org_id=current_user["org_id"],
                    workflow_instance_id=instance.workflow_instance_id,
                    workflow_task_id=task.workflow_task_id,
                    reminder_sent_by=current_user["user_id"],
                    reminder_sent_to=user_id,
                    reminder_message=reminder_message,
                    sent_at=now,
                    notification_status="PENDING",
                )
            )

        task.reminder_count += 1
        task.last_reminder_at = now
        task.updated_by = current_user["user_id"]
        task.updated_at = now
        await db.commit()

        await self._notif_client.send({
            "type": "WORKFLOW_REMINDER",
            "workflow_task_id": task.workflow_task_id,
            "workflow_instance_id": instance.workflow_instance_id,
            "message": reminder_message,
            "recipients": recipients,
        })

        return {"message": "Reminder sent", "recipients": recipients}

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _create_task(
        self,
        db: AsyncSession,
        instance: WorkflowInstance,
        node: WorkflowNode,
        assignees: list[int],
        current_user: dict,
        now: datetime,
    ) -> WorkflowTask:
        due_at = (
            now + timedelta(hours=node.sla_hours) if node.sla_hours else None
        )
        task = WorkflowTask(
            org_id=current_user["org_id"],
            workflow_instance_id=instance.workflow_instance_id,
            workflow_id=instance.workflow_id,
            node_id=node.node_id,
            task_status="PENDING",
            assignment_type=node.assignment_type,
            assignment_strategy=node.assignment_strategy,
            assigned_to_user_id=assignees[0] if len(assignees) == 1 else None,
            assigned_to_role_id=node.assigned_role_id,
            due_at=due_at,
            created_by=current_user["user_id"],
            created_at=now,
            is_active=True,
            is_deleted=False,
        )
        db.add(task)
        await db.flush()

        # For ALL_USERS strategy: create candidate rows for pool-based claiming
        if len(assignees) > 1:
            for user_id in assignees:
                db.add(
                    WorkflowTaskCandidate(
                        org_id=current_user["org_id"],
                        workflow_task_id=task.workflow_task_id,
                        user_id=user_id,
                        created_by=current_user["user_id"],
                        created_at=now,
                        is_active=True,
                        is_deleted=False,
                    )
                )
        return task

    async def _resolve_transition(
        self,
        db: AsyncSession,
        instance: WorkflowInstance,
        current_node: WorkflowNode,
        action_code: str,
        payload: dict,
    ) -> WorkflowTransition:
        """
        Evaluates conditional transitions in priority order.
        Falls back to is_default=True if no condition matches.
        """
        transitions = (
            await db.execute(
                select(WorkflowTransition).where(
                    WorkflowTransition.workflow_id == instance.workflow_id,
                    WorkflowTransition.from_node_id == current_node.node_id,
                    WorkflowTransition.action_code == action_code,
                    WorkflowTransition.is_active == True,
                    WorkflowTransition.is_deleted == False,
                ).order_by(WorkflowTransition.priority.asc())
            )
        ).scalars().all()

        if not transitions:
            raise BusinessException(
                f"No transition found for action '{action_code}' from node '{current_node.node_name}'",
                code="TRANSITION_NOT_FOUND",
                status_code=400,
            )

        # Merge instance metadata with action payload for expression evaluation
        ctx = {**(instance.metadata_json or {}), **payload}

        default_transition = None
        for t in transitions:
            if t.is_default:
                default_transition = t
                continue
            if t.condition_expression:
                try:
                    if eval(t.condition_expression, {"__builtins__": {}}, ctx):  # noqa: S307
                        return t
                except Exception:
                    continue  # skip broken expressions
            else:
                # No condition and not default → immediate match
                return t

        if default_transition:
            return default_transition

        raise BusinessException(
            f"No matching transition for action '{action_code}' from node '{current_node.node_name}'",
            code="TRANSITION_NOT_FOUND",
            status_code=400,
        )

    async def _get_task_assignees(
        self, db: AsyncSession, task: WorkflowTask
    ) -> list[int]:
        if task.assigned_to_user_id:
            return [task.assigned_to_user_id]
        candidates = (
            await db.execute(
                select(WorkflowTaskCandidate).where(
                    WorkflowTaskCandidate.workflow_task_id == task.workflow_task_id,
                    WorkflowTaskCandidate.is_deleted == False,
                )
            )
        ).scalars().all()
        return [c.user_id for c in candidates]

    @staticmethod
    def _map_end_status(node_type: str) -> str:
        mapping = {
            "END_APPROVED": "APPROVED",
            "END_REJECTED": "REJECTED",
            "END_CANCELLED": "CANCELLED",
        }
        return mapping.get(node_type.upper(), "COMPLETED")