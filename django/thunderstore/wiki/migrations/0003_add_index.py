# Generated by Django 3.1.7 on 2023-03-27 05:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thunderstore_wiki", "0002_add_index"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="wiki",
            options={"ordering": ("datetime_updated",)},
        ),
        migrations.AddIndex(
            model_name="wiki",
            index=models.Index(
                fields=["datetime_updated"], name="thunderstor_datetim_967b06_idx"
            ),
        ),
    ]
