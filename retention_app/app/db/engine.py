from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


DATABASE_URL = "sqlite:///./app.db"


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ensure_schema_compatibility() -> None:
    """Best-effort schema patching for local SQLite upgrades without Alembic.

    Existing users may already have an `app.db` created before new columns were added.
    `create_all()` cannot alter existing tables, so we add missing columns in-place.
    """
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "content_text" not in inspector.get_table_names():
            return

        existing_columns = {
            column["name"] for column in inspector.get_columns("content_text")
        }
        expected_columns = {
            "raw_transcript": "TEXT",
            "corrected_transcript": "TEXT",
            "ocr_text_corpus": "TEXT",
            "correction_annotations": "TEXT",
        }

        for column_name, column_type in expected_columns.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                text(
                    f"ALTER TABLE content_text ADD COLUMN {column_name} {column_type}"
                )
            )
