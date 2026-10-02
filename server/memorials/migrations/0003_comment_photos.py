import django.db.models.deletion
import memorials.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorials', '0002_ceremony_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='relationship',
            field=models.CharField(blank=True, max_length=100, verbose_name='lien avec le défunt'),
        ),
        migrations.CreateModel(
            name='CommentPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(height_field='height', upload_to=memorials.models.comment_photo_path, verbose_name='photo', width_field='width')),
                ('width', models.PositiveIntegerField(default=0, editable=False)),
                ('height', models.PositiveIntegerField(default=0, editable=False)),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='memorials.comment', verbose_name='message')),
            ],
            options={
                'verbose_name': 'photo',
                'verbose_name_plural': 'photos',
                'ordering': ['pk'],
            },
        ),
    ]
