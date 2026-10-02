import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorials', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='memorial',
            name='ceremony',
            field=models.TextField(blank=True, help_text='Facultatif : fleurs, dons, « ni fleurs ni couronnes »… Les étapes de la cérémonie se saisissent dans le tableau « Étapes de la cérémonie » plus bas.', verbose_name='informations complémentaires'),
        ),
        migrations.CreateModel(
            name='CeremonyStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Ex. : Levée du corps, Cérémonie religieuse, Inhumation, Crémation, Réunion après la cérémonie.', max_length=120, verbose_name='étape')),
                ('starts_at', models.DateTimeField(blank=True, null=True, verbose_name='date et heure')),
                ('place', models.CharField(blank=True, help_text='Ex. : Église Saint-Germain', max_length=160, verbose_name='lieu')),
                ('address', models.CharField(blank=True, help_text='Sert au lien « Itinéraire » vers Google Maps.', max_length=255, verbose_name='adresse')),
                ('details', models.CharField(blank=True, help_text='Ex. : dans l’intimité familiale', max_length=255, verbose_name='précisions')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='ordre')),
                ('memorial', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='memorials.memorial', verbose_name='avis')),
            ],
            options={
                'verbose_name': 'étape de la cérémonie',
                'verbose_name_plural': 'étapes de la cérémonie',
                'ordering': ['order', 'starts_at', 'pk'],
            },
        ),
    ]
