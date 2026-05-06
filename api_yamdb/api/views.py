from django.contrib.auth.tokens import default_token_generator
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


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    """Регистрация и повторная отправка кода."""
    serializer = CustomUserCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    username = serializer.validated_data.get("username")
    email = serializer.validated_data.get("email")

    user_by_username = User.objects.filter(username=username).first()
    user_by_email = User.objects.filter(email=email).first()

    if user_by_username:
        if user_by_username.email != email:
            return Response(
                {"username": "Этот ник уже занят другим email"},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = user_by_username
    elif user_by_email:
        return Response(
            {"email": "Этот email уже занят другим пользователем"},
            status=status.HTTP_400_BAD_REQUEST
        )
    else:
        user = User.objects.create_user(username=username, email=email)

    confirmation_code = default_token_generator.make_token(user)

    send_mail(
        "Код подтверждения YaMDb",
        f"Ваш код: {confirmation_code}",
        None,
        [email],
        fail_silently=True,
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def get_jwt_token(request):
    """Получение JWT токена."""
    username = request.data.get("username")
    confirmation_code = request.data.get("confirmation_code")

    if not username or not confirmation_code:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, username=username)

    if not default_token_generator.check_token(user, confirmation_code):
        return Response(
            {"confirmation_code": "Неверный код"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token = RefreshToken.for_user(user).access_token
    return Response({"token": str(token)}, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """Управление пользователями."""

    queryset = User.objects.all()
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
        serializer.save(role=request.user.role)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreateListDestroyViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Базовый вьюсет для Категорий и Жанров."""


class CategoryViewSet(CreateListDestroyViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ("name",)
    lookup_field = "slug"


class GenreViewSet(CreateListDestroyViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ("name",)
    lookup_field = "slug"


class TitleViewSet(viewsets.ModelViewSet):
    """Произведения."""

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
    """Отзывы."""

    serializer_class = ReviewSerializer
    permission_classes = (IsAuthorOrModeratorOrAdmin,)
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        title = get_object_or_404(Title, pk=self.kwargs.get("title_id"))
        return title.reviews.select_related("author")

    def perform_create(self, serializer):
        title = get_object_or_404(Title, pk=self.kwargs.get("title_id"))
        serializer.save(author=self.request.user, title=title)


class CommentViewSet(viewsets.ModelViewSet):
    """Комментарии."""

    serializer_class = CommentSerializer
    permission_classes = (IsAuthorOrModeratorOrAdmin,)
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        review = get_object_or_404(
            Review,
            pk=self.kwargs.get("review_id"),
            title_id=self.kwargs.get("title_id"),
        )
        return review.comments.select_related("author")

    def perform_create(self, serializer):
        review = get_object_or_404(
            Review,
            pk=self.kwargs.get("review_id"),
            title_id=self.kwargs.get("title_id"),
        )
        serializer.save(author=self.request.user, review=review)
