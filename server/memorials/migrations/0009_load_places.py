"""Add the churches, funeral homes and crematoriums around Soisy and Saint-Leu (memorials/data/places.json).

Places already in the list are left as they are. After editing the file, run it again with
python manage.py migrate memorials 0008 && python manage.py migrate"""

import json
from pathlib import Path

from django.db import migrations

PLACES = Path(__file__).resolve().parent.parent / "data" / "places.json"


def load(apps, schema_editor):
	Place = apps.get_model("memorials", "Place")
	for place in json.loads(PLACES.read_text(encoding="utf-8")):
		Place.objects.get_or_create(name=place["name"], address=place["address"])


class Migration(migrations.Migration):
	dependencies = [("memorials", "0008_fill_saved_places")]
	operations = [migrations.RunPython(load, migrations.RunPython.noop)]
