from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail

db = SQLAlchemy()
migrate = Migrate() 
mail = Mail()

# Add connection health check to prevent "MySQL server has gone away" errors
try:
    from sqlalchemy import event
    from sqlalchemy.pool import Pool
    
    @event.listens_for(Pool, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Check connection health before using - helps prevent stale connection errors"""
        try:
            # Try to ping the connection to check if it's alive
            # If ping fails, connection will be recreated automatically
            if hasattr(dbapi_conn, 'ping'):
                dbapi_conn.ping(reconnect=True)
        except Exception:
            # If ping fails, let SQLAlchemy handle reconnection
            pass
except ImportError:
    # SQLAlchemy event system not available, skip
    pass 