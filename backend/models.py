from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.text("now()"),
    )


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=db.text("gen_random_uuid()"),
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename = db.Column(db.Text, nullable=False)
    stored_filename = db.Column(db.Text, nullable=True)
    test_date = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.Text,
        nullable=False,
        server_default=db.text("'uploaded'"),
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.text("now()"),
    )


class Biomarker(db.Model):
    __tablename__ = "biomarkers"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)


class BiomarkerResult(db.Model):
    __tablename__ = "biomarker_results"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=db.text("gen_random_uuid()"),
    )
    report_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    biomarker_id = db.Column(
        db.BigInteger,
        db.ForeignKey("biomarkers.id"),
        nullable=False,
    )
    value = db.Column(db.Numeric, nullable=False)
    unit = db.Column(db.Text, nullable=True)
    reference_low = db.Column(db.Numeric, nullable=True)
    reference_high = db.Column(db.Numeric, nullable=True)
    flag = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.text("now()"),
    )
