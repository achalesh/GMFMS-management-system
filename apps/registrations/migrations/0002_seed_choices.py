from django.db import migrations


def seed(apps, schema_editor):
    model = apps.get_model("registrations", 'Skill')
    for index, (code, name) in enumerate([('photography', 'Photography'), ('videography', 'Videography'), ('video-editing', 'Video Editing'), ('graphic-design', 'Graphic Design'), ('content-writing', 'Content Writing'), ('reporting', 'Reporting'), ('news-reading', 'News Reading'), ('social-media-management', 'Social Media Management'), ('live-streaming', 'Live Streaming'), ('drone-operation', 'Drone Operation'), ('audio-editing', 'Audio Editing'), ('other', 'Other')]):
        model.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={"name":name,"display_order":index})
    model = apps.get_model("registrations", 'Equipment')
    for index, (code, name) in enumerate([('smartphone', 'Smartphone'), ('laptop', 'Laptop'), ('desktop', 'Desktop'), ('dslrmirrorless-camera', 'DSLR/Mirrorless Camera'), ('video-camera', 'Video Camera'), ('tripod', 'Tripod'), ('microphone', 'Microphone'), ('gimbal', 'Gimbal'), ('lighting-equipment', 'Lighting Equipment'), ('drone', 'Drone'), ('internet-connection', 'Internet Connection'), ('other', 'Other')]):
        model.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={"name":name,"display_order":index})
    model = apps.get_model("registrations", 'Language')
    for index, (code, name) in enumerate([('malayalam', 'Malayalam'), ('english', 'English'), ('hindi', 'Hindi'), ('tamil', 'Tamil'), ('other', 'Other')]):
        model.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={"name":name,"display_order":index})
    model = apps.get_model("registrations", "DocumentType")
    for index, (code,name) in enumerate([('recommendation', 'Panchayat recommendation / authorization'), ('identity', 'Applicant identity proof'), ('certificate', 'Supporting certificate'), ('other', 'Other supporting document')]):
        model.objects.using(schema_editor.connection.alias).get_or_create(code=code,defaults={"name":name,"display_order":index})


class Migration(migrations.Migration):
    dependencies = [("registrations","0001_initial")]
    operations = [migrations.RunPython(seed,migrations.RunPython.noop)]
