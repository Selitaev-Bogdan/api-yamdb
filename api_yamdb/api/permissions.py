from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """Права доступа: администратор или только чтение."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_superuser
        )


class IsAdmin(permissions.BasePermission):
    """Права доступа: только администратор."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin or request.user.is_superuser
        )


class IsAuthorOrModeratorOrAdmin(permissions.BasePermission):
    """Права доступа: автор, модератор или администратор."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (
            request.user == obj.author
            or request.user.is_moderator
            or request.user.is_admin
            or request.user.is_superuser
        )
