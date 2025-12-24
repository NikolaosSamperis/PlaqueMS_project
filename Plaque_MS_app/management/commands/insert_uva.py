from django.core.management.base import BaseCommand, CommandError
from Plaque_MS_app.insert_views import insert_three_logic
from Plaque_MS_app.models import Datasets

class Command(BaseCommand):
    help = "Import the University of Virginia Coronary Arteries Cohort into the database"

    def handle(self, *args, **options):
        self.stdout.write("🟢 Starting UVA cohort import...")
        try:
            insert_three_logic()
        except Datasets.DoesNotExist:
            raise CommandError("Dataset 'Coronary Arteries University of Virginia Cohort' does not exist.")
        self.stdout.write(self.style.SUCCESS("✅ UVA import complete."))