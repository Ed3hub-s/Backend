from rest_framework.permissions import BasePermission


def is_educator(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or getattr(getattr(user, 'profile', None), 'role', None) == 'educator')
    )


class IsEducator(BasePermission):
    message = 'Only educator accounts can manage live classes.'

    def has_permission(self, request, view):
        return is_educator(request.user)


class IsLiveClassOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.educator_id == request.user.id
