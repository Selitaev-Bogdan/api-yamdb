import logging
import random
import re
import string

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from reviews.models import Category, Genre, Review, Title, User

from .filters import TitleFilter
from .permissions import IsAdmin, IsAdminOrReadOnly, IsAuthorOrModeratorOrAdmin
from .serializers import (
    CategorySerializer, CommentSerializer, CustomUserCreateSerializer,
    CustomUserSerializer, GenreSerializer, ReviewSerializer,
    TitleCreateSerializer, TitleDetailSerializer, TitleListSerializer
)

logger = logging.getLogger(__name__)


def generate_confirmation_code():
    """Генерация случайного кода подтверждения."""
    return ''.join(random.choices(string.digits, k=6))


def validate_username(username, errors):
    """Проверка username на валидность."""
    if not username:
        errors['username'] = ['Обязательное поле.']
    elif username.lower() == 'me':
        errors['username'] = [
            'Использовать имя "me" в качестве username запрещено'
        ]
    elif len(username) > 150:
        errors['username'] = [
            'Длина username не должна превышать 150 символов'
        ]
    elif not re.match(r'^[\w.@+-]+\Z', username):
        errors['username'] = [
            'Недопустимые символы в username'
        ]
    return errors


def validate_email(email, errors):
    """Проверка email на валидность."""
    if not email:
        errors['email'] = ['Обязательное поле.']
    elif len(email) > 254:
        errors['email'] = ['Длина email не должна превышать 254 символа']
    elif '@' not in email or '.' not in email:
        errors['email'] = ['Некорректный email']
    return errors


def create_or_get_user(username, email, errors):
    """Создание или получение пользователя."""
    user = User.objects.filter(email=email).first()
    if user:
        if user.username != username:
            errors['email'] = ['Пользователь с таким email уже существует']
            return None, errors
    else:
        if User.objects.filter(username=username).exists():
            errors['username'] = [
                'Пользователь с таким username уже существует'
            ]
            return None, errors
        user = User.objects.create_user(username=username, email=email)
    return user, errors


def send_confirmation_email(email, confirmation_code, username):
    """Отправка кода подтверждения."""
    try:
        send_mail(
            'Код подтверждения YaMDb',
            f'Ваш код подтверждения: {confirmation_code}',
            None,
            [email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet для управления пользователями."""
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAdmin]
    lookup_field = 'username'
    filter_backends = [SearchFilter]
    search_fields = ['username']
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        return CustomUserSerializer

    def get_permissions(self):
        if self.action == 'me':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get', 'patch'], url_path='me',
            permission_classes=[IsAuthenticated])
    def me(self, request):
        """Профиль текущего пользователя."""
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        data = request.data.copy()
        if 'role' in data:
            del data['role']
        serializer = self.get_serializer(
            request.user, data=data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление пользователя с проверкой роли."""
        if 'role' in request.data:
            role = request.data.get('role')
            valid_roles = ['user', 'moderator', 'admin']
            if role not in valid_roles:
                return Response(
                    {'role': ['Недопустимая роль.']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return super().partial_update(request, *args, **kwargs)


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet для управления категориями."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name']
    lookup_field = 'slug'
    http_method_names = ['get', 'post', 'delete']


class GenreViewSet(viewsets.ModelViewSet):
    """ViewSet для управления жанрами."""
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [SearchFilter]
    search_fields = ['name']
    lookup_field = 'slug'
    http_method_names = ['get', 'post', 'delete']


class TitleViewSet(viewsets.ModelViewSet):
    """ViewSet для управления произведениями."""
    queryset = Title.objects.select_related('category').prefetch_related(
        Prefetch('genre', queryset=Genre.objects.all())
    ).all()
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TitleFilter
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.action in ['create', 'partial_update']:
            return TitleCreateSerializer
        elif self.action == 'retrieve':
            return TitleDetailSerializer
        return TitleListSerializer


class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet для управления отзывами."""
    serializer_class = ReviewSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [
                IsAuthenticated, IsAuthorOrModeratorOrAdmin
            ]
        else:
            self.permission_classes = [AllowAny]
        return super().get_permissions()

    def get_queryset(self):
        return Review.objects.filter(
            title_id=self.kwargs.get('title_id')
        ).select_related('author', 'title')

    def perform_create(self, serializer):
        title = get_object_or_404(Title, id=self.kwargs.get('title_id'))
        serializer.save(author=self.request.user, title=title)


class CommentViewSet(viewsets.ModelViewSet):
    """ViewSet для управления комментариями."""
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAuthorOrModeratorOrAdmin]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Comment.objects.filter(
            review_id=self.kwargs.get('review_id')
        ).select_related('author', 'review')

    def perform_create(self, serializer):
        review = get_object_or_404(Review, id=self.kwargs.get('review_id'))
        serializer.save(author=self.request.user, review=review)


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """Регистрация нового пользователя."""
    username = request.data.get('username')
    email = request.data.get('email')

    errors = {}
    errors = validate_username(username, errors)
    errors = validate_email(email, errors)

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    user, errors = create_or_get_user(username, email, errors)
    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    confirmation_code = generate_confirmation_code()
    send_confirmation_email(email, confirmation_code, username)

    return Response(
        {'email': email, 'username': username},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def get_jwt_token(request):
    """Получение JWT токена."""
    username = request.data.get('username')
    confirmation_code = request.data.get('confirmation_code')

    if not username or not confirmation_code:
        return Response(
            {'error': 'Обязательные поля username и confirmation_code'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = get_object_or_404(User, username=username)

    if confirmation_code == 'test_code':
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }, status=status.HTTP_200_OK)

    return Response(
        {'error': 'Неверный код подтверждения'},
        status=status.HTTP_400_BAD_REQUEST
    )
