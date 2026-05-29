from django import forms


class NewsletterContactCSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV file',
        help_text='Required column: email. Optional columns: first_name, last_name, name, source, is_subscribed.',
    )
    source = forms.CharField(max_length=120, required=False, initial='csv-import')
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Update names, source, and subscription status when an email already exists.',
    )
