from app.database import engine, Base
from app.models import trainer, trainer_application, announcement

Base.metadata.create_all(bind=engine, tables=[
    trainer.Trainer.__table__,
    trainer_application.TrainerApplication.__table__,
    announcement.Announcement.__table__,
])
print("All tables created successfully")
