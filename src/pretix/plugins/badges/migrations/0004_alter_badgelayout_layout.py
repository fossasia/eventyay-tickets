# Generated by Django 5.1.4 on 2025-03-10 18:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('badges', '0003_alter_badgeitem_id_alter_badgelayout_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='badgelayout',
            name='layout',
            field=models.TextField(
                default='[{"type":"textarea","left":"0","bottom":"85","fontsize":"12.0","color":[0,0,0,1],"fontfamily":"Open Sans","bold":true,"italic":false,"width":"80","content":"attendee_name","text":"John Doe","align":"center"},{"type":"barcodearea","left":"24.87","bottom":"34","size":"30.00","content":"secret"},{"type":"textarea","left":"0","bottom":"83","fontsize":"10.0","color":[0,0,0,1],"fontfamily":"Open Sans","bold":false,"italic":false,"width":"80.00","downward":true,"content":"attendee_job_title","text":"Developer","align":"center"},{"type":"textarea","left":"0","bottom":"76","fontsize":"12.0","color":[0,0,0,1],"fontfamily":"Open Sans","bold":false,"italic":false,"width":"80","downward":true,"content":"attendee_company","text":"FOSSASIA","align":"center"}]'
            ),
        ),
    ]
