from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from authentication.newsletter_import import import_newsletter_contacts


class Command(BaseCommand):
    help = 'Import external newsletter contacts from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)
        parser.add_argument('--source', type=str, default='csv-import')
        parser.add_argument('--imported-by', type=str, default='', help='Username of the admin importing the contacts.')
        parser.add_argument('--skip-existing', action='store_true', help='Do not update contacts that already exist.')

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path'])
        if not csv_path.exists():
            raise CommandError(f'CSV file not found: {csv_path}')
        if not csv_path.is_file():
            raise CommandError(f'CSV path is not a file: {csv_path}')

        imported_by = None
        username = options['imported_by']
        if username:
            User = get_user_model()
            try:
                imported_by = User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f'User not found for --imported-by: {username}') from exc

        with csv_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
            result = import_newsletter_contacts(
                csv_file,
                source=options['source'],
                imported_by=imported_by,
                update_existing=not options['skip_existing'],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Import completed. Created: {result.created}. Updated: {result.updated}. Skipped: {result.skipped}.'
            )
        )
        for error in result.errors[:20]:
            self.stdout.write(self.style.WARNING(error))
        if len(result.errors) > 20:
            self.stdout.write(self.style.WARNING(f'{len(result.errors) - 20} more warning(s) not shown.'))
