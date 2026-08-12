import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_app", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AftercareTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("introduction", models.TextField(blank=True)),
                ("approved_by", models.CharField(blank=True, help_text="Interne fachliche Freigabe; keine automatische medizinische Empfehlung", max_length=140)),
                ("version", models.CharField(default="1.0", max_length=20)),
                ("active", models.BooleanField(default=True)),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p1_aftercare_templates", to="platform_app.service")),
            ],
            options={"ordering": ["service__name", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BeautyPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("journey_type", models.CharField(choices=[("custom", "Individuell"), ("wedding", "Wedding"), ("birthday", "Birthday Glow"), ("summer", "Summer"), ("winter", "Winter Skin"), ("travel", "Travel"), ("photoshoot", "Photoshoot"), ("event", "Special Event"), ("hair", "Hair Recovery"), ("skin", "Skin Reset")], default="custom", max_length=20)),
                ("goal", models.TextField(blank=True)),
                ("target_date", models.DateField(blank=True, null=True)),
                ("monthly_budget_cents", models.PositiveIntegerField(default=0)),
                ("annual_budget_cents", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("draft", "Entwurf"), ("active", "Aktiv"), ("completed", "Abgeschlossen"), ("archived", "Archiviert")], default="draft", max_length=15)),
                ("medical_decision_support", models.BooleanField(default=False, editable=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p1_beauty_plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="ProgressAlbum",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("marketing_use_allowed", models.BooleanField(default=False, editable=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p1_progress_albums", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AftercareTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("task_type", models.CharField(choices=[("do", "Empfohlen"), ("avoid", "Vermeiden"), ("contact", "A+ kontaktieren")], max_length=15)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("warning_sign", models.BooleanField(default=False)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="p1_app.aftercaretemplate")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="AssignedAftercare",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("appointment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p1_assigned_aftercare", to="platform_app.appointment")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="p1_app.aftercaretemplate")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p1_assigned_aftercare", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-starts_at"]},
        ),
        migrations.CreateModel(
            name="BeautyPlanStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("due_on", models.DateField(blank=True, null=True)),
                ("step_type", models.CharField(choices=[("care", "Pflege"), ("product", "Produkt"), ("consultation", "Beratung anfragen"), ("appointment", "Organisatorischer Termin"), ("content", "Lerninhalt")], max_length=20)),
                ("estimated_cost_cents", models.PositiveIntegerField(default=0)),
                ("completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="p1_app.beautyplan")),
            ],
            options={"ordering": ["sort_order", "due_on", "id"]},
        ),
        migrations.CreateModel(
            name="ProgressPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("before", "Vorher"), ("after", "Nachher"), ("progress", "Verlauf")], max_length=12)),
                ("image", models.FileField(upload_to="progress/%Y/%m/")),
                ("taken_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("sha256", models.CharField(editable=False, max_length=64)),
                ("visible_to_customer", models.BooleanField(default=True)),
                ("album", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="p1_app.progressalbum")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="p1_uploaded_progress_photos", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["taken_at", "id"]},
        ),
        migrations.CreateModel(
            name="AftercareTaskStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("assigned", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="task_statuses", to="p1_app.assignedaftercare")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="p1_app.aftercaretask")),
            ],
            options={"ordering": ["task__sort_order", "id"]},
        ),
        migrations.AddConstraint(model_name="aftercaretemplate", constraint=models.UniqueConstraint(fields=("service", "version"), name="p1_aftercare_service_version")),
        migrations.AddConstraint(model_name="assignedaftercare", constraint=models.UniqueConstraint(fields=("appointment", "template"), name="p1_unique_aftercare_assignment")),
        migrations.AddConstraint(model_name="aftercaretaskstatus", constraint=models.UniqueConstraint(fields=("assigned", "task"), name="p1_unique_aftercare_task_status")),
    ]
