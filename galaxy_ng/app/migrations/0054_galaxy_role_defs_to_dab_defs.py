import logging
import time

from django.db import migrations

from django.apps import apps as global_apps

from ansible_base.rbac.management import create_dab_permissions
from ansible_base.rbac.migrations._utils import give_permissions

logger = logging.getLogger(__name__)


def create_permissions_as_operation(apps, schema_editor):
    # TODO: possibly create permissions for more apps here
    create_dab_permissions(global_apps.get_app_config("galaxy"), apps=apps)

    print(f'FINISHED CREATING PERMISSIONS')


def reverse_create_permissions_as_operation(apps, schema_editor):
    Permission = apps.get_model('dab_rbac', 'DABPermission')
    for perm in Permission.objects.all():
        print(f'DELETE {perm} {perm.codename}')
        perm.delete()


def split_pulp_roles(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    UserRole = apps.get_model('core', 'UserRole')
    GroupRole = apps.get_model('core', 'GroupRole')

    for corerole in Role.objects.all():
        split_roles = {}
        for assignment_cls in (UserRole, GroupRole):
            for pulp_assignment in assignment_cls.objects.filter(role=corerole, content_type__isnull=False):
                if pulp_assignment.content_type_id not in split_roles:
                    new_data = {
                        'description': corerole.description,
                        'name': f'{corerole.name}_{pulp_assignment.content_type.model}'
                    }
                    new_role = Role(**new_data)
                    new_role.save()
                    split_roles[pulp_assignment.content_type_id] = new_role
            pulp_assignment.role = split_roles[pulp_assignment.content_type_id]
            pulp_assignment.save(update_fields=['role'])


def copy_roles_to_role_definitions(apps, schema_editor):
    Role = apps.get_model('core', 'Role')
    DABPermission = apps.get_model('dab_rbac', 'DABPermission')
    RoleDefinition = apps.get_model('dab_rbac', 'RoleDefinition')

    for corerole in Role.objects.all():
        print(f'CREATE {corerole} {corerole.name}')
        roledef, _ = RoleDefinition.objects.get_or_create(name=corerole.name)

        content_types = set()
        for perm in corerole.permissions.all():
            dabperm = DABPermission.objects.filter(
                codename=perm.codename,
                content_type=perm.content_type,
                name=perm.name
            ).first()
            if dabperm:
                roledef.permissions.add(dabperm)
                content_types.add(perm.content_type)

        if roledef.permissions.count() == 0:
            print(f'Role {corerole.name} has no DAB RBAC permissions so not migrating it')
            roledef.delete()  # oh well


def migrate_role_assignments(apps, schema_editor):
    UserRole = apps.get_model('core', 'UserRole')
    GroupRole = apps.get_model('core', 'GroupRole')
    RoleDefinition = apps.get_model('dab_rbac', 'RoleDefinition')
    RoleUserAssignment = apps.get_model('dab_rbac', 'RoleUserAssignment')
    RoleTeamAssignment = apps.get_model('dab_rbac', 'RoleTeamAssignment')

    for user_role in UserRole.objects.all():
        rd = RoleDefinition.objects.filter(name=user_role.role.name).first()
        if not rd:
            continue
        if not user_role.object_id:
            # system role
            RoleUserAssignment.objects.create(role_definition=rd, user=user_role.user)
        else:
            give_permissions(apps, rd, users=[user_role.user], object_id=user_role.object_id, content_type_id=user_role.content_type_id)

    for group_role in GroupRole.objects.all():
        rd = RoleDefinition.objects.filter(name=group_role.role.name).first()
        if not rd:
            continue
        actor = group_role.group.team
        if not group_role.object_id:
            RoleTeamAssignment.objects.create(role_definition=rd, team=actor)
        else:
            give_permissions(apps, rd, teams=[actor], object_id=group_role.object_id, content_type_id=group_role.content_type_id)


def reverse_copy_roles_to_role_definitions(apps, schema_editor):
    RoleDefinition = apps.get_model('dab_rbac', 'RoleDefinition')
    for roledef in RoleDefinition.objects.all():
        print(f'DELETE {roledef} {roledef.name}')
        roledef.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0117_task_unblocked_at'),
        ('ansible', '0055_alter_collectionversion_version_alter_role_version'),
        ('galaxy', '0053_wait_for_dab_rbac'),
        ('dab_rbac', '__first__'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="team",
            options={
                "ordering": ("organization__name", "name"),
                "permissions": [("member_team", "Has all permissions granted to this team")],
            },
        ),
        migrations.AlterModelOptions(
            name="organization",
            options={
                "permissions": [("member_organization", "User is a member of this organization")]
            },
        ),
        migrations.RunPython(
            create_permissions_as_operation,
            reverse_create_permissions_as_operation
        ),
        migrations.RunPython(split_pulp_roles, migrations.RunPython.noop),
        migrations.RunPython(
            copy_roles_to_role_definitions,
            reverse_copy_roles_to_role_definitions
        ),
        migrations.RunPython(migrate_role_assignments, migrations.RunPython.noop)
    ]
