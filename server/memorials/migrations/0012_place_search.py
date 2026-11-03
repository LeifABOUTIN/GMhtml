from django.db import migrations, models

from memorials.models import searchable


def fill(apps, schema_editor):
	for place in apps.get_model("memorials", "Place").objects.all():
		place.search = searchable(" ".join([place.title, place.name, place.address]))
		place.save(update_fields=["search"])


class Migration(migrations.Migration):
	dependencies = [("memorials", "0011_place_title")]
	operations = [
		migrations.AddField("place", "search", models.CharField(blank=True, editable=False, max_length=700)),
		migrations.RunPython(fill, migrations.RunPython.noop),
	]
