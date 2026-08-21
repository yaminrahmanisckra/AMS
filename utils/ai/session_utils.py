"""Keep MySQL usable around long-running AI HTTP calls."""


def reset_db_session():
    """Rollback and drop the scoped session so the next query gets a live connection.

    Outline generation holds a Flask request open for tens of seconds while talking
    to the AI provider. Shared-host MySQL closes that idle connection, and the next
    INSERT then fails with "MySQL server has gone away" plus PendingRollbackError.
    """
    try:
        from flask import has_app_context
        if not has_app_context():
            return
        from extensions import db
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            db.session.remove()
        except Exception:
            pass
    except Exception:
        pass
