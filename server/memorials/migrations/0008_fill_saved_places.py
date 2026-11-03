"""Start the list of saved places with the addresses already used in ceremony steps."""

from django.db import migrations


def fill(apps, schema_editor):
	Place = apps.get_model("memorials", "Place")
	for step in apps.get_model("memorials", "CeremonyStep").objects.exclude(address=""):
		step.saved_place, _ = Place.objects.get_or_create(name=step.place, address=step.address)
		step.save(update_fields=["saved_place"])


class Migration(migrations.Migration):
	dependencies = [("memorials", "0007_saved_places")]
	operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
