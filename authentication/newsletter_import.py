import csv
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import NewsletterContact


TRUE_VALUES = {'1', 'true', 'yes', 'y', 'on', 'subscribed'}
FALSE_VALUES = {'0', 'false', 'no', 'n', 'off', 'unsubscribed'}


@dataclass
class NewsletterContactImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self):
        return self.created + self.updated + self.skipped


def parse_subscription(value):
    if value is None or str(value).strip() == '':
        return True

    normalized_value = str(value).strip().lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False
    return True


def split_name(name):
    parts = (name or '').strip().split(None, 1)
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], parts[1]


def import_newsletter_contacts(rows, *, source='csv-import', imported_by=None, update_existing=True):
    reader = csv.DictReader(rows)
    result = NewsletterContactImportResult()

    if not reader.fieldnames:
        result.errors.append('CSV file has no header row.')
        return result

    fieldnames = {field.strip().lower() for field in reader.fieldnames if field}
    if 'email' not in fieldnames:
        result.errors.append('CSV file must include an email column.')
        return result

    for row_number, row in enumerate(reader, start=2):
        normalized_row = {
            (key or '').strip().lower(): (value or '').strip()
            for key, value in row.items()
        }
        email = normalized_row.get('email', '').lower()
        if not email:
            result.skipped += 1
            result.errors.append(f'Row {row_number}: missing email.')
            continue

        try:
            validate_email(email)
        except ValidationError:
            result.skipped += 1
            result.errors.append(f'Row {row_number}: invalid email "{email}".')
            continue

        first_name = normalized_row.get('first_name', '')
        last_name = normalized_row.get('last_name', '')
        if not first_name and not last_name and normalized_row.get('name'):
            first_name, last_name = split_name(normalized_row.get('name'))

        row_source = normalized_row.get('source') or source or 'csv-import'
        defaults = {
            'first_name': first_name,
            'last_name': last_name,
            'source': row_source,
            'is_subscribed': parse_subscription(normalized_row.get('is_subscribed')),
            'imported_by': imported_by,
        }

        contact = NewsletterContact.objects.filter(email=email).first()
        if contact:
            if not update_existing:
                result.skipped += 1
                continue
            for key, value in defaults.items():
                setattr(contact, key, value)
            contact.save(update_fields=[*defaults.keys(), 'updated_at'])
            result.updated += 1
        else:
            NewsletterContact.objects.create(email=email, **defaults)
            result.created += 1

    return result
