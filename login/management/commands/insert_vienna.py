from django.core.management.base import BaseCommand, CommandError
from login.insert_views import insert_two_logic
from login.models import Datasets

class Command(BaseCommand):
    help = "Import the Carotid Plaques Vienna Cohort into the database"

    def handle(self, *args, **options):
        self.stdout.write("🟢 Starting Vienna cohort import...")
        try:
            # Ensure the dataset exists, then run logic
            insert_two_logic()
        except Datasets.DoesNotExist:
            raise CommandError("Dataset 'Carotid Plaques Vienna Cohort' does not exist.")
        self.stdout.write(self.style.SUCCESS("✅ Vienna import complete."))
