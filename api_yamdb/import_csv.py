import csv
import os

import django
from reviews.models import Category, Comment, Genre, Review, Title, User

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api_yamdb.settings')
django.setup()


def import_categories():
    with open('static/data/category.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            Category.objects.update_or_create(
                id=row['id'],
                defaults={'name': row['name'], 'slug': row['slug']}
            )
    print(f'Categories imported: {Category.objects.count()}')


def import_genres():
    with open('static/data/genre.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            Genre.objects.update_or_create(
                id=row['id'],
                defaults={'name': row['name'], 'slug': row['slug']}
            )
    print(f'Genres imported: {Genre.objects.count()}')


def import_users():
    with open('static/data/users.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            User.objects.update_or_create(
                id=row['id'],
                defaults={
                    'username': row['username'],
                    'email': row['email'],
                    'role': row['role']
                }
            )
    print(f'Users imported: {User.objects.count()}')


def import_titles():
    with open('static/data/titles.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            category = Category.objects.get(id=row['category'])
            Title.objects.update_or_create(
                id=row['id'],
                defaults={
                    'name': row['name'],
                    'year': row['year'],
                    'category': category
                }
            )
    print(f'Titles imported: {Title.objects.count()}')


def import_genre_title_relations():
    with open('static/data/genre_title.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            title = Title.objects.get(id=row['title_id'])
            genre = Genre.objects.get(id=row['genre_id'])
            title.genre.add(genre)
    print('Genre-title relations imported')


def import_reviews():
    with open('static/data/review.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            title = Title.objects.get(id=row['title_id'])
            author = User.objects.get(id=row['author'])
            Review.objects.update_or_create(
                id=row['id'],
                defaults={
                    'title': title,
                    'author': author,
                    'text': row['text'],
                    'score': row['score'],
                    'pub_date': row['pub_date']
                }
            )
    print(f'Reviews imported: {Review.objects.count()}')


def import_comments():
    with open('static/data/comments.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            review = Review.objects.get(id=row['review_id'])
            author = User.objects.get(id=row['author'])
            Comment.objects.update_or_create(
                id=row['id'],
                defaults={
                    'review': review,
                    'author': author,
                    'text': row['text'],
                    'pub_date': row['pub_date']
                }
            )
    print(f'Comments imported: {Comment.objects.count()}')


if __name__ == '__main__':
    print('Starting import...')
    import_categories()
    import_genres()
    import_users()
    import_titles()
    import_genre_title_relations()
    import_reviews()
    import_comments()
    print('Import completed!')
