from django.db import models

class ParentalRating(models.Model):

    rating = models.CharField(max_length=40)

    def __unicode__(self):
        return '{0}'.format(self.rating)

class Genre(models.Model):

    name = models.CharField(max_length=50)

    def __unicode__(self):
        return '{0}'.format(self.name)

class Movie(models.Model):

    title = models.CharField(max_length=100, db_index=True)

    bechdel_rating = models.IntegerField(db_index=True)
    bechdel_disputed = models.NullBooleanField()

    imdb_id = models.CharField(max_length=40, null=True, blank=True)
    imdb_rating = models.FloatField(null=True, blank=True, db_index=True)

    tomato_meter = models.IntegerField(null=True, blank=True)
    tomato_fresh = models.IntegerField(null=True, blank=True)
    tomato_rotten = models.IntegerField(null=True, blank=True)
    tomato_user_meter = models.IntegerField(null=True, blank=True)
    tomato_user_rating = models.FloatField(null=True, blank=True)

    year = models.IntegerField(null=True, blank=True, db_index=True)
    box_office_receipts = models.IntegerField(null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    writer = models.CharField(max_length=100, null=True, blank=True)
    director = models.CharField(max_length=100, null=True, blank=True)
    actors = models.CharField(max_length=255, null=True, blank=True)
    plot = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    awards = models.CharField(max_length=255, null=True, blank=True)
    poster = models.CharField(max_length=255, null=True, blank=True)

    parental_rating = models.ForeignKey(ParentalRating, related_name='parental_rating', null=True, blank=True)
    genre = models.ManyToManyField(Genre, related_name='genre', null=True, blank=True)

    # Auto-generated timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{0}'.format(self.title)

class Search(models.Model):

    search = models.CharField(max_length=100)

    # Auto-generated timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{0}'.format(self.search)