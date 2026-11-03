from django.db import migrations, models

from memorials.models import place_title


def fill(apps, schema_editor):
	for place in apps.get_model("memorials", "Place").objects.all():
		place.title = place_title(place.name, place.address)
		place.save(update_fields=["title"])


class Migration(migrations.Migration):
	dependencies = [("memorials", "0010_family_emails_help")]
	operations = [
		migrations.AddField("place", "title", models.CharField("titre", max_length=200, blank=True,
			help_text="Nom affiché dans la liste de choix, ex. : Église de Soisy. Laissé vide : « lieu (ville) ».")),
		migrations.AlterField("place", "name", models.CharField("lieu", max_length=160,
			help_text="Affiché sur la page de l’avis. Ex. : Église Saint-Germain")),
		migrations.AlterModelOptions("place", {"ordering": ["title", "name", "address"],
			"verbose_name": "lieu enregistré", "verbose_name_plural": "lieux enregistrés"}),
		migrations.RunPython(fill, migrations.RunPython.noop),
	]
