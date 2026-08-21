from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()

# Recreate dead pooled connections instead of using them (MySQL "server has gone away").
try:
    from sqlalchemy import event
    from sqlalchemy.exc import DisconnectionError
    from sqlalchemy.pool import Pool

    @event.listens_for(Pool, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        try:
            if hasattr(dbapi_conn, 'ping'):
                dbapi_conn.ping(reconnect=True)
        except Exception as exc:
            raise DisconnectionError() from exc
except ImportError:
    pass 