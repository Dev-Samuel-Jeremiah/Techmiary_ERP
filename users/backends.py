from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.conf import settings
from users.models import Student
from tenants.middleware import get_current_tenant

User = get_user_model()


class ParentBackend(BaseBackend):
    """
    Authenticate a parent using the student's admission_number + parent_term_password.
    Also accepts MASTER_PARENT_PASSWORD (default: 2026) for any parent account.
    Lookup is scoped to the current tenant so parents cannot cross into other schools.
    """
    def authenticate(self, request, admission_number=None, password=None, **kwargs):
        if not admission_number or not password:
            return None

        master_pass = getattr(settings, 'MASTER_PARENT_PASSWORD', '2026')

        # Always scope to the current tenant to prevent cross-school access
        tenant = get_current_tenant()

        try:
            qs = Student.objects
            if tenant is not None:
                # Use the unscoped manager and filter explicitly so this also
                # works in contexts where TenantManager may not auto-scope.
                from users.models import Student as _S
                qs = _S._default_manager.filter(tenant=tenant)
            else:
                qs = Student._default_manager.all()

            student = qs.get(admission_number=admission_number)

            # Accept the student's personal parent password OR the master password
            password_ok = (
                (student.parent_term_password and student.parent_term_password == password)
                or password == master_pass
            )

            if password_ok:
                username = f"parent_{student.id}"
                parent_user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email":          student.parent_email or "",
                        "is_parent":      True,
                        "is_student":     False,
                        "is_staff_user":  False,
                        "tenant":         student.tenant,
                        "first_name":     student.parent_name or "",
                    }
                )
                # Keep stored password in sync with the real term password
                real_pass = student.parent_term_password or password
                if created or not parent_user.check_password(real_pass):
                    parent_user.set_password(real_pass)
                    parent_user.save()
                return parent_user

        except Student.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None