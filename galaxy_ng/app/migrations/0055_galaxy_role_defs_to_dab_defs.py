import logging

from django.db import migrations

from django.apps import apps as global_apps

from ansible_base.rbac.management import create_dab_permissions

logger = logging.getLogger(__name__)


def create_permissions_as_operation(apps, schema_editor):
    create_dab_permissions(global_apps.get_app_config("galaxy"), apps=apps)
    Permission = apps.get_model('auth', 'Permission')
    DABPermission = apps.get_model('dab_rbac', 'DABPermission')
    for perm in Permission.objects.all():
        print(f'CREATE {perm}')
        dab_perm, created = DABPermission.objects.get_or_create(
            codename=perm.codename,
            content_type=perm.content_type,
            name=perm.name
        )


def reverse_create_permissions_as_operation(apps, schema_editor):
    Permission = apps.get_model('dab_rbac', 'DABPermission')
    for perm in Permission.objects.all():
        print(f'DELETE {perm}')
        perm.delete()


def copy_permissions_to_role_definitions(apps, schema_editor):
    Permission = apps.get_model('dab_rbac', 'DABPermission')
    RoleDefinition = apps.get_model('dab_rbac', 'RoleDefinition')

    '''
    # TODO: migrate from pulp role model or something like that
    permissions = Permission.objects.all().filter(name__icontains='namespace')
    rd, created = RoleDefinition.objects.get_or_create(
        name='Namespace Admin',
        defaults=dict(
            content_type=permissions[0].content_type,
            managed=True
        )
    )
    if created:
        logger.info(f'Created RoleDefinition {rd.name}')
        for perm in permissions:
            rd.permissions.add(perm)
    '''


def reverse_copy_permissions_to_role_definitions(apps, schema_editor):
    RoleDefinition = apps.get_model('dab_rbac', 'RoleDefinition')
    for roledef in RoleDefinition.objects.all():
        print(f'DELTE {roledef}')
        roledef.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('galaxy', '0054_dab_resource_views'),
        ('dab_rbac', '__first__'),
    ]

    operations = [
        migrations.RunPython(
            create_permissions_as_operation,
            reverse_create_permissions_as_operation
        ),
        migrations.RunPython(
            copy_permissions_to_role_definitions,
            reverse_copy_permissions_to_role_definitions
        ),
    ]
