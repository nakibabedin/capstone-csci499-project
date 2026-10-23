from app import app, db, User, Report, Biomarker, BiomarkerResult

try:
    with app.app_context():
        models = [User, Report, Biomarker, BiomarkerResult]

        for model in models:
            db.session.query(model).limit(0).all()
            print("Table mapping works:", model.__tablename__)

except Exception as error:
    print("Database check failed:", type(error).__name__)