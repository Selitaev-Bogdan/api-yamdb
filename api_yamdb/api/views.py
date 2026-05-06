import random
import string

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from reviews.models import Category, Genre, Review, Title, User

from .filters import TitleFilter
from .permissions import IsAdmin, IsAdminOrReadOnly, IsAuthorOrModeratorOrAdmin
from .serializers import (CategorySerializer, CommentSerializer,
                          CustomUserCreateSerializer, CustomUserSerializer,
                          GenreSerializer, ReviewSerializer,
                          TitleCreateSerializer, TitleListSerializer)


def generate_confirmation_code():
    return "".join(random.choices(string.digits, k=6))


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    """Регистрация и повторная отправка кода."""
    serializer = CustomUserCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    username = serializer.validated_data.get("username")
    email = serializer.validated_data.get("email")

    # Оптимизация: получаем пользователя одним запросом
    user = User.objects.filter(username=username, email=email).first()

    if not user:
        if User.objects.filter(username=username).exists():
            return Response(
                {"username": "Это имя уже занято"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email=email).exists():
            return Response(
                {"email": "Этот email уже занят"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.create(username=username, email=email)

    confirmation_code = generate_confirmation_code()
    user.confirmation_code = confirmation_code
    user.save()

    send_mail(
        "Код подтверждения YaMDb",
        f"Ваш код: {confirmation_code}",
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=True,
    )
    return Response(
        {"username": username, "email": email}, status=status.HTTP_200_OK
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def get_jwt_token(request):
    """Получение JWT токена. Использование Guard Clauses."""
    username = request.data.get("username")
    confirmation_code = request.data.get("confirmation_code")

    if not username or not confirmation_code:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, username=username)

    if confirmation_code != user.confirmation_code:
        return Response(
            {"confirmation_code": "Неверный код"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token = RefreshToken.for_user(user).access_token
    return Response({"token": str(token)}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """Управление пользователями."""

    queryset = User.objects.all().order_by("username")
    serializer_class = CustomUserSerializer
    permission_classes = (IsAdmin,)
    lookup_field = "username"
    filter_backends = (filters.SearchFilter,)
    search_fields = ("username",)
    http_method_names = ["get", "post", "patch", "delete"]

    @action(
        detail=False,
        methods=["get", "patch"],
        url_path="me",
        permission_classes=(IsAuthenticated,),
    )
    def me(self, request):
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        # Ревью: используем метод модели is_admin вместо прямой строки
        serializer.save(role=request.user.role)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateListDestroyViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Базовый вьюсет для Категорий и Жанров."""

    pass


class CategoryViewSet(CreateListDestroyViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ("name",)
    lookup_field = "slug"


class GenreViewSet(CreateListDestroyViewSet):
    queryset = Genre.objects.all().order_by("name")
    serializer_class = GenreSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ("name",)
    lookup_field = "slug"


class TitleViewSet(viewsets.ModelViewSet):
    """Произведения. Оптимизированный QuerySet."""

    queryset = (
        Title.objects.annotate(rating=Avg("reviews__score"))
        .select_related("category")
        .prefetch_related("genre")
        .order_by("name")
    )
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TitleFilter
    http_method_names = ["get", "post", "patch", "delete"]

    def get_serializer_class(self):
        if self.action in ("create", "partial_update"):
            return TitleCreateSerializer
        return TitleListSerializer


class ReviewViewSet(viewsets.ModelViewSet):
    """Отзывы. Оптимизация через select_related."""

    serializer_class = ReviewSerializer
    permission_classes = (IsAuthorOrModeratorOrAdmin,)
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        title = get_object_or_404(Title, pk=self.kwargs.get("title_id"))
        return title.reviews.select_related("author").all()

    def perform_create(self, serializer):
        title = get_object_or_404(Title, pk=self.kwargs.get("title_id"))
        serializer.save(author=self.request.user, title=title)


class CommentViewSet(viewsets.ModelViewSet):
    """Комментарии. Оптимизация через select_related."""

    serializer_class = CommentSerializer
    permission_classes = (IsAuthorOrModeratorOrAdmin,)
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        review = get_object_or_404(
            Review,
            pk=self.kwargs.get("review_id"),
            title_id=self.kwargs.get("title_id"),
        )
        return review.comments.select_related("author").all()

    def perform_create(self, serializer):
        review = get_object_or_404(
            Review,
            pk=self.kwargs.get("review_id"),
            title_id=self.kwargs.get("title_id"),
        )
        serializer.save(author=self.request.user, review=review)
