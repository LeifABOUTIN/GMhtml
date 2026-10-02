import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('site', 'Site (écrit ici)'), ('facebook', 'Facebook'), ('instagram', 'Instagram')], default='site', max_length=10, verbose_name='origine')),
                ('external_id', models.CharField(blank=True, editable=False, max_length=100, verbose_name='identifiant Facebook/Instagram')),
                ('title', models.CharField(blank=True, help_text='Laissé vide : la première phrase du texte est utilisée.', max_length=200, verbose_name='titre')),
                ('slug', models.SlugField(blank=True, max_length=120, unique=True, verbose_name='adresse de la page')),
                ('text', models.TextField(blank=True, verbose_name='texte')),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date')),
                ('permalink', models.URLField(blank=True, max_length=500, verbose_name='lien vers la publication d’origine')),
                ('is_video', models.BooleanField(default=False, help_text='La vidéo n’est pas copiée : un lien vers Facebook/Instagram est affiché.', verbose_name='contient une vidéo')),
                ('is_published', models.BooleanField(default=True, verbose_name='publié')),
                ('locked', models.BooleanField(default=False, help_text='Coché automatiquement quand vous modifiez une publication importée : l’import quotidien ne touchera plus ni le texte, ni la visibilité.', verbose_name='ne plus mettre à jour automatiquement')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ajouté le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='modifié le')),
            ],
            options={
                'verbose_name': 'actualité',
                'verbose_name_plural': 'actualités',
                'ordering': ['-published_at'],
                'constraints': [models.UniqueConstraint(condition=models.Q(('external_id', ''), _negated=True), fields=('source', 'external_id'), name='unique_social_post')],
            },
        ),
        migrations.CreateModel(
            name='PostImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(height_field='height', upload_to='actualites/%Y/', verbose_name='image', width_field='width')),
                ('width', models.PositiveIntegerField(default=0, editable=False)),
                ('height', models.PositiveIntegerField(default=0, editable=False)),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='ordre')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='news.post', verbose_name='actualité')),
            ],
            options={
                'verbose_name': 'image',
                'verbose_name_plural': 'images',
                'ordering': ['order', 'pk'],
            },
        ),
    ]
