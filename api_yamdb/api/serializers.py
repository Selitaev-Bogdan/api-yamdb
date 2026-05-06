from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers
from reviews.models import Category, Comment, Genre, Review, Title, User


class CustomUserSerializer(serializers.ModelSerializer):
    """Сериализатор для модели User."""

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "bio",
            "role",
        )


class CustomUserCreateSerializer(serializers.Serializer):
    """Сериализатор для регистрации."""

    email = serializers.EmailField(required=True, max_length=254)
    username = serializers.CharField(
        required=True, max_length=150, validators=[UnicodeUsernameValidator()]
    )

    def validate_username(self, value):
        if value.lower() == "me":
            raise serializers.ValidationError('Имя "me" запрещено.')
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name", "slug")


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("name", "slug")


class TitleListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка произведений."""

    category = CategorySerializer(read_only=True)
    genre = GenreSerializer(many=True, read_only=True)
    rating = serializers.IntegerField(read_only=True)

    class Meta:
        model = Title
        fields = (
            "id",
            "name",
            "year",
            "rating",
            "description",
            "category",
            "genre",
        )


class TitleCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания произведений."""

    category = serializers.SlugRelatedField(
        slug_field="slug", queryset=Category.objects.all()
    )
    genre = serializers.SlugRelatedField(
        slug_field="slug", queryset=Genre.objects.all(), many=True
    )

    class Meta:
        model = Title
        fields = ("id", "name", "year", "description", "category", "genre")


class ReviewSerializer(serializers.ModelSerializer):
    """Сериализатор для отзывов."""

    author = serializers.SlugRelatedField(
        slug_field="username", read_only=True
    )

    class Meta:
        model = Review
        fields = ("id", "text", "author", "score", "pub_date")

    def validate(self, data):
        request = self.context.get("request")
        if request.method != "POST":
            return data

        title_id = self.context["view"].kwargs.get("title_id")
        if Review.objects.filter(
            title_id=title_id, author=request.user
        ).exists():
            raise serializers.ValidationError("Вы уже оставили отзыв.")
        return data


class CommentSerializer(serializers.ModelSerializer):
    """Сериализатор для комментариев."""

    author = serializers.SlugRelatedField(
        slug_field="username", read_only=True
    )

    class Meta:
        model = Comment
        fields = ("id", "text", "author", "pub_date")
