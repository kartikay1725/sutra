from sqlalchemy import select

from app.models.task_event import TaskEvent


def test_agent_task_claim_creates_task_event(
    client,
    db,
):
    from tests.test_agent_tasks import (
        make_agent,
        make_repository,
        make_task,
        make_user,
        create_session,
        bearer,
        get_task,
    )

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

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 200

    events = db.scalars(
        select(TaskEvent)
        .where(
            TaskEvent.task_id == task.id,
            TaskEvent.event_type == TaskEvent.EVENT_CLAIMED,
        )
    ).all()

    assert len(events) == 1

    event = events[0]

    saved_task = get_task(
        db,
        task.id,
    )

    assert event.task_id == task.id
    assert event.actor_id == agent.id
    assert event.session_id is not None
    assert (
        event.session_id
        == saved_task.claimed_by_session_id
    )
    assert event.to_status == "in_progress"
    assert event.from_status == "assigned"