from app.db.session import SessionLocal
from app.services.git_push_event_processor import GitPushEventProcessor


def main() -> None:
    db = SessionLocal()

    try:
        processor = GitPushEventProcessor(db)
        events = processor.process_pending()

        print(
            f"SUTRA Git push event processor: "
            f"processed {len(events)} event(s)."
        )

        for event in events:
            print(
                f"{event.id} "
                f"status={event.status} "
                f"attempts={event.attempts}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()