from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db.models import Avg
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from reviews.models import Category, Comment, Genre, Review, Title, User


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'bio', 'role')
        read_only_fields = ('role',)

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('name', 'slug')

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ('name', 'slug')

class TitleListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    genre = GenreSerializer(many=True, read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Title
        fields = ('id', 'name', 'year', 'rating', 'description', 'category', 'genre')

    def get_rating(self, obj):
        rating = obj.reviews.aggregate(Avg('score'))['score__avg']
        return round(rating, 1) if rating else None

class TitleDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    genre = GenreSerializer(many=True, read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = Title
        fields = ('id', 'name', 'year', 'rating', 'description', 'category', 'genre')

    def get_rating(self, obj):
        rating = obj.reviews.aggregate(Avg('score'))['score__avg']
        return round(rating, 1) if rating else None

class TitleCreateSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field='slug',
        queryset=Category.objects.all()
    )
    genre = serializers.SlugRelatedField(
        slug_field='slug',
        queryset=Genre.objects.all(),
        many=True
    )

    class Meta:
        model = Title
        fields = ('id', 'name', 'year', 'description', 'category', 'genre')

    def create(self, validated_data):
        genres = validated_data.pop('genre')
        title = Title.objects.create(**validated_data)
        title.genre.set(genres)
        return title

    def update(self, instance, validated_data):
        if 'category' in validated_data:
            instance.category = validated_data['category']
        if 'name' in validated_data:
            instance.name = validated_data['name']
        if 'year' in validated_data:
            instance.year = validated_data['year']
        if 'description' in validated_data:
            instance.description = validated_data['description']
        if 'genre' in validated_data:
            genres = validated_data.pop('genre')
            instance.genre.set(genres)
        instance.save()
        return instance

class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True
    )

    class Meta:
        model = Review
        fields = ('id', 'text', 'author', 'score', 'pub_date')

    def validate(self, data):
        request = self.context['request']
        if request.method == 'POST' and request.user.is_authenticated:
            title_id = self.context['view'].kwargs.get('title_id')
            if Review.objects.filter(
                title_id=title_id,
                author=request.user
            ).exists():
                raise serializers.ValidationError('Вы уже оставили отзыв')
        return data

class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True
    )

    class Meta:
        model = Comment
        fields = ('id', 'text', 'author', 'pub_date')

class CustomUserCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        max_length=254,                    # ← важно
        validators=[
            UniqueValidator(queryset=User.objects.all())
        ]
    )
    username = serializers.CharField(
        required=True,
        max_length=150,                    # ← важно
        validators=[
            UnicodeUsernameValidator(),    # ← ^[\w.@+-]+\Z
            UniqueValidator(queryset=User.objects.all())
        ]
    )
    password = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True
    )
    role = serializers.ChoiceField(
        choices=['user', 'moderator', 'admin'], 
        required=False, 
        default='user'
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'role', 'first_name', 'last_name', 'bio')

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['role'] = instance.role
        return representation
