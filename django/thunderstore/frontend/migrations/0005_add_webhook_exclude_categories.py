# Generated by Django 3.0.4 on 2020-09-08 07:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('frontend', '0004_dynamichtml_ordering'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dynamichtml',
            name='placement',
            field=models.CharField(choices=[('ads_txt', 'ads_txt'), ('robots_txt', 'robots_txt'), ('html_head', 'html_head'), ('html_body_beginning', 'html_body_beginning'), ('content_beginning', 'content_beginning'), ('content_end', 'content_end')], db_index=True, max_length=256),
        ),
    ]
