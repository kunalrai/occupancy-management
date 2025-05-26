from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class BadgeAccess(db.Model):
    __tablename__ = 'badge_access'
    
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), nullable=False)
    global_id = db.Column(db.String(50), nullable=False)
    initial_login_date = db.Column(db.Date, nullable=False)
    badge_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Ensure unique combination of global_id and initial_login_date
    __table_args__ = (
        db.UniqueConstraint('global_id', 'initial_login_date', name='unique_gid_login_date'),
    )

    def __repr__(self):
        return f'<BadgeAccess {self.global_id} - {self.initial_login_date}>'