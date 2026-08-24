from app.database.connection import init_db
from app.database.models import models
print("Creating new tables...")
init_db()
print("Done.")
