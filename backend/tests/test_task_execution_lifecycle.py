from sqlalchemy import select

from app.models.task import Task
from app.models.task_event import TaskEvent

from tests.test_agent_tasks import (
    bearer,
    create_session,
    get_task,
    make_agent,
    make_repository,
    make_task,
    make_user,
)


def test_claim_and_execute_create_task_events(
    client,
    db,
):
    owner = make_user(db)

    agent, raw_token = make_agent(
        db,
        owner.id,
    )

    repository = make_repository(
        db,
        owner,
    )

    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    execute = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert execute.status_code == 200

    events = db.scalars(
        select(TaskEvent)
        .where(
            TaskEvent.task_id == task.id,
        )
        .order_by(TaskEvent.created_at.asc())
    ).all()

    event_types = [
        event.event_type
        for event in events
    ]

    assert TaskEvent.EVENT_CLAIMED in event_types
    assert TaskEvent.EVENT_CHANGE_CREATED in event_types

    claimed = next(
        event
        for event in events
        if event.event_type
        == TaskEvent.EVENT_CLAIMED
    )

    assert claimed.actor_id == agent.id
    assert claimed.session_id == session["session_id"]

    change_created = next(
        event
        for event in events
        if event.event_type
        == TaskEvent.EVENT_CHANGE_CREATED
    )

    assert change_created.actor_id == agent.id
    assert (
        change_created.session_id
        == session["session_id"]
    )
