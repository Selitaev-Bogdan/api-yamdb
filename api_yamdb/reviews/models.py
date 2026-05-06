import datetime as dt

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from api_yamdb.constants import (MAX_LENGTH_EMAIL, MAX_LENGTH_NAME,
                                 MAX_LENGTH_ROLE, MAX_LENGTH_USERNAME,
                                 MAX_SCORE, MIN_SCORE)


class Roles(models.TextChoices):
    USER = "user", "Пользователь"
    MODERATOR = "moderator", "Модератор"
    ADMIN = "admin", "Администратор"


class User(AbstractUser):
    email = models.EmailField(
        "Электронная почта", max_length=MAX_LENGTH_EMAIL, unique=True
    )
    username = models.CharField(
        "Имя пользователя",
        max_length=MAX_LENGTH_USERNAME,
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )
    role = models.CharField(
        "Роль",
        max_length=MAX_LENGTH_ROLE,
        choices=Roles.choices,
        default=Roles.USER,
    )
    bio = models.TextField("Биография", blank=True, null=True)

    class Meta:
        ordering = ("username",)
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.username

    @property
    def is_admin(self):
        return self.role == Roles.ADMIN or self.is_superuser

    @property
    def is_moderator(self):
        return self.role == Roles.MODERATOR


class Category(models.Model):
    name = models.CharField("Название", max_length=MAX_LENGTH_NAME)
    slug = models.SlugField("Слаг", unique=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Genre(models.Model):
    name = models.CharField("Название", max_length=MAX_LENGTH_NAME)
    slug = models.SlugField("Слаг", unique=True)

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Title(models.Model):
    name = models.CharField("Название", max_length=MAX_LENGTH_NAME)
    year = models.PositiveSmallIntegerField(
        "Год выпуска",
        validators=[
            MaxValueValidator(
                dt.datetime.now().year,
                message="Год выпуска не может быть больше текущего"
            )
        ]
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="titles",
        verbose_name="Категория",
    )
    genre = models.ManyToManyField(
        Genre, related_name="titles", verbose_name="Жанр"
    )
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Произведение"
        verbose_name_plural = "Произведения"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Review(models.Model):
    title = models.ForeignKey(
        Title,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Произведение",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Автор",
    )
    text = models.TextField("Текст отзыва")
    score = models.PositiveSmallIntegerField(
        "Оценка",
        validators=[
            MinValueValidator(MIN_SCORE),
            MaxValueValidator(MAX_SCORE),
        ],
    )
    pub_date = models.DateTimeField("Дата публикации", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["title", "author"], name="unique_review"
            )
        ]
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ("-pub_date",)

    def __str__(self):
        return f"{self.author} - {self.title}"


class Comment(models.Model):
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Отзыв",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Автор",
    )
    text = models.TextField("Текст комментария")
    pub_date = models.DateTimeField("Дата публикации", auto_now_add=True)

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ("-pub_date",)

    def __str__(self):
        return f"{self.author} - {self.review}"
