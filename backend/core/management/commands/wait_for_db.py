import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = "Wait until the database is accepting connections."

    def handle(self, *args, **options):
        self.stdout.write("Waiting for database...")
        db_conn = None
        attempts = 0
        while not db_conn:
            try:
                db_conn = connections["default"]
                db_conn.ensure_connection()
            except OperationalError:
                attempts += 1
                if attempts > 30:
                    self.stderr.write("Database did not become available in 30 seconds.")
                    raise
                time.sleep(1)
        self.stdout.write(self.style.SUCCESS("Database available."))