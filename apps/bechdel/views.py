import datetime
import random
import requests

from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.conf import settings

from apps.bechdel.models import Movie, ParentalRating, Genre, Search

class HomeView(TemplateView):

    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super(HomeView, self).get_context_data(**kwargs)
        total_movies = Movie.objects.count()
        context['total_movies'] = total_movies
        return context

class SearchView(TemplateView):

    ''' Show choices when more than one movie has been returned for the query.
    '''

    template_name = 'select.html'

    def post(self, request, **kwargs):

        query = request.POST.get('q')

        if not query:
            try:
                query = request.GET.get('q')
            except:
                query = False

        if not query:
            messages.error(request, 'Please enter your search.')
            return HttpResponseRedirect('/bechdel')
        else:
            if not ''.join([q for q in query if q.isalpha() or q.isdigit()]):
                # Eliminate other bad queries
                messages.error(request, 'Please enter your search.')
                return HttpResponseRedirect('/bechdel')

        query = query.replace("'", '&#39;').replace('<', '').replace('>', '')

        if query.isdigit() or query[:2] == 'tt':
            # Query is an imdb ID; do a direct lookup
            bechdel_request_url = 'http://bechdeltest.com/api/v1/getMovieByImdbId?imdbid={0}'.format(query)
            direct_lookup = True
        else:
            # Remove the word 'The ' from queries to improve searching.
            if query[:4].lower() == 'the ':
                query = query[4:]
            bechdel_request_url = 'http://bechdeltest.com/api/v1/getMoviesByTitle?title={0}'.format(query.replace(' ', '+'))
            direct_lookup = False

        # Save the search query
        if len(query) > 100:
            query = query[:100]

        new_search = Search(search=query)
        new_search.save()

        try:
            bechdel_response = requests.get(bechdel_request_url).json()
        except:
            messages.error(request, 
                '''An error occurred while searching the Bechdel Test API for {0}.  
                Please try again.'''.format(query)
                )
            return HttpResponseRedirect('/bechdel')

        if direct_lookup:
            # Direct Lookup returns JSON, title search returns a list of items
            bechdel_response = [bechdel_response]

        if len(bechdel_response) == 0:
            messages.error(request, 
                '''The movie you searched for, {0}, was not found. 
                Either the movie does not exist in the Bechdel Test API database, 
                or your search was too complex.  Please try again.
                '''.format(query))
            return HttpResponseRedirect('/bechdel')
        else:
            # Loop through each response item, add to database
            for movie in bechdel_response:
                
                # Check to see whether it exists already in the database
                if movie.get('imdbid'):
                    try:
                        existing_movie = Movie.objects.get(imdb_id=movie['imdbid'])
                    except MultipleObjectsReturned:
                        # In rare cases, more than one movie will be returned.
                        # In these cases, we will not update the database.
                        pass
                    except ObjectDoesNotExist:
                        # This movie is not yet in the database, so add it.
                        new_movie_details = {
                            'title': movie.get('title', '').replace('&#39;', "'")[:100],
                            'year': movie.get('year'),
                            'bechdel_rating': movie.get('rating'),
                            'bechdel_disputed': bool(int(movie.get('dubious'))),
                            'imdb_id': movie.get('imdbid'),
                        }
                        new_movie = Movie(**new_movie_details)
                        new_movie.save()
                    else:
                        # Update info (except Title) if any has changed
                        if existing_movie != movie.get('year') and movie.get('year'):
                            existing_movie.year = movie.get('year')

                        if existing_movie.bechdel_rating != movie.get('rating') and movie.get('rating'):
                            existing_movie.bechdel_rating = int(movie.get('rating'))

                        try:
                            if existing_movie.bechdel_disputed != bool(int(movie.get('dubious'))):
                                existing_movie.bechdel_disputed = bool(int(movie.get('dubious')))
                        except:
                            existing_movie.bechdel_disputed = None

                        existing_movie.save()

        if len(bechdel_response) == 1:
            context = {}
            try:
                movie = Movie.objects.get(imdb_id=bechdel_response[0].get('imdbid'))
            except MultipleObjectsReturned:
                # Just get the first result. It's probably fine.
                movie = Movie.objects.filter(imdb_id=bechdel_response[0].get('imdbid'))[0]
                return HttpResponseRedirect('/bechdel/movie/{0}'.format(movie.id))
            except ObjectDoesNotExist:
                messages.error(request, 'An error occurred.  Please try your search again.')
                return HttpResponseRedirect('/bechdel')
            else:
                return HttpResponseRedirect('/bechdel/movie/{0}'.format(movie.id))
        elif len(bechdel_response) > 1:
            # Show choices for when more than one movie has been returned for the query.
            messages.info(request, '{0} movies matched your search.  Which were you looking for?'.format(len(bechdel_response)))

            movies = []
            for movie in bechdel_response:
                try:
                    movies.append(Movie.objects.get(imdb_id=movie.get('imdbid')))
                except:
                    pass

            context = {
                'movies': movies,
            }

        context['total_movies'] = Movie.objects.count()

        return render(request, self.template_name, context)

    get = post

class MovieView(TemplateView):

    ''' Show the summary page for one movie.
    '''

    template_name = 'movie.html'

    bechdel_rating_explanations = {
        '0': (messages.error, "this movie doesn't even have two women in it.  Wow."),
        '1': (messages.warning, "this movie has two women in it, but they don't even talk to one another."),
        '2': (messages.info, "this movie has two women in it, but they only talk to one another about a man."),
        '3': (messages.success, "this movie has two women in it who talk to one another -- about something other than a man!")
    }

    bechdel_dispute_explanation = {
        'disputed': ' ... however, this rating has been disputed.',
        'undisputed': ''
    }

    def get(self, request, **kwargs):

        try:
            movie_id = int(kwargs.get('id'))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid movie ID: {0}, please try again.'.format(request.GET.get('id')))
            return HttpResponseRedirect('/bechdel')

        try:
            movie = Movie.objects.get(id=movie_id)
        except ObjectDoesNotExist:
            messages.error(request, 'Movie ID #{0} not found in our system, please try again.'.format(movie_id))
            return HttpResponseRedirect('/bechdel')

        context = self.get_context_data(**{'id': movie_id,
            'movie': movie,
            'request': request})

        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):

        movie_id = kwargs.get('id')
        movie = kwargs.get('movie')
        request = kwargs.get('request')

        last_updated = datetime.datetime.now(movie.updated_at.tzinfo) - movie.updated_at

        if last_updated.days >= 90 or (movie.updated_at - movie.created_at).days < 3:
            # Request info from the OMDB API
            try:
                omdb_response = requests.get('https://www.omdbapi.com/?i={0}{1}&y={2}&apikey={3}&tomatoes=true'.format('tt' if 'tt' not in movie.imdb_id[:2] else '', movie.imdb_id, movie.year, settings.OMDBAPI_KEY)).json()
            except:
                # If the omdb request failed, that's okay -- continue with the information we do have
                pass
            else:
                # If any information is different, update it in the database.

                # "Genre":"Action, Comedy, Romance"
                omdb_response_genres = omdb_response.get('Genre', '').split(',')

                if omdb_response_genres[0] != '':
                    for omdb_response_genre in omdb_response_genres:
                        genre = Genre.objects.filter(name=omdb_response_genre.strip())[0]
                        if genre not in movie.genre.all():
                            movie.genre.add(genre)

                # OMDB Title should take precedence over Bechdel API Title
                if movie.title != omdb_response.get('Title') and omdb_response.get('Title'):
                    movie.title = omdb_response.get('Title', '')[:100]

                if movie.parental_rating != omdb_response.get('Rated') and omdb_response.get('Rated'):
                    try:
                        movie.parental_rating = ParentalRating.objects.get(rating=omdb_response.get('Rated'))
                    except ObjectDoesNotExist:
                        movie.parental_rating = ParentalRating.objects.get(id=7) # Unrated / Not rated

                if movie.runtime != omdb_response.get('Runtime') and omdb_response.get('Runtime'):
                    # Assume minutes
                    try:
                        movie.runtime = int(''.join([i for i in omdb_response.get('Runtime', '') if i.isdigit()]))
                    except:
                        pass

                if movie.director != omdb_response.get('Director') and omdb_response.get('Director'):
                    movie.director = omdb_response.get('Director', '')[:100]

                if movie.writer != omdb_response.get('Writer') and omdb_response.get('Writer'):
                    movie.writer = omdb_response.get('Writer', '')[:100]

                if movie.actors != omdb_response.get('Actors') and omdb_response.get('Actors'):
                    movie.actors = omdb_response.get('Actors', '')[:255]

                if movie.plot != omdb_response.get('Plot') and omdb_response.get('Plot'):
                    movie.plot = omdb_response.get('Plot', '')[:255]

                if movie.country != omdb_response.get('Country') and omdb_response.get('Country'):
                    movie.country = omdb_response.get('Country', '')[:100]

                if movie.awards != omdb_response.get('Awards') and omdb_response.get('Awards'):
                    movie.awards = omdb_response.get('Awards', '')[:255]

                if movie.poster != omdb_response.get('Poster') and omdb_response.get('Poster'):
                    movie.poster = omdb_response.get('Poster', '')[:255]

                if movie.box_office_receipts != omdb_response.get('BoxOffice') and omdb_response.get('BoxOffice'):
                    try:
                        omdb_response['BoxOffice'] = int(omdb_response['BoxOffice'].replace('$','').replace('M','00000').replace('.',''))
                    except:
                        pass
                    else:
                        if omdb_response['BoxOffice'] > 0:
                            movie.box_office_receipts = omdb_response['BoxOffice']

                if movie.imdb_rating != omdb_response.get('imdbRating') and omdb_response.get('imdbRating'):
                    try:
                        movie.imdb_rating = float(omdb_response.get('imdbRating'))
                    except:
                        pass

                if movie.tomato_meter != omdb_response.get('tomatoMeter') and omdb_response.get('tomatoMeter'):
                    try:
                        movie.tomato_meter = int(omdb_response.get('tomatoMeter'))
                    except:
                        pass

                if movie.tomato_fresh != omdb_response.get('tomatoFresh') and omdb_response.get('tomatoFresh'):
                    try:
                        movie.tomato_fresh = int(omdb_response.get('tomatoFresh'))
                    except:
                        pass

                if movie.tomato_rotten != omdb_response.get('tomatoRotten') and omdb_response.get('tomatoRotten'):
                    try:
                        movie.tomato_rotten = int(omdb_response.get('tomatoRotten'))
                    except:
                        pass

                if movie.tomato_user_meter != omdb_response.get('tomatoUserMeter') and omdb_response.get('tomatoUserMeter'):
                    try:
                        movie.tomato_user_meter = int(omdb_response.get('tomatoUserMeter'))
                    except:
                        pass

                if movie.tomato_user_rating != omdb_response.get('tomatoUserRating') and omdb_response.get('tomatoUserRating'):
                    try:
                        movie.tomato_meter = float(omdb_response.get('tomatoUserRating'))
                    except:
                        pass

                movie.save()

        # Send the message for this movie
        self.bechdel_rating_explanations[str(movie.bechdel_rating)][0](request,
            u'''{0} has a Bechdel rating of {1}/3. That means {2} {3}'''.format(
                movie.title, movie.bechdel_rating, 
                self.bechdel_rating_explanations[str(movie.bechdel_rating)][1],
                self.bechdel_dispute_explanation['disputed'] if movie.bechdel_disputed else self.bechdel_dispute_explanation['undisputed']
                )
            )

        context = {
            'movie': movie,
            'total_movies': Movie.objects.count()
        }

        if movie.bechdel_rating == 3:
            context['title'] = "Other movies you may enjoy"
        else:
            context['title'] = "Watch these instead"

        try:
            float(movie.imdb_rating)
        except:
            # This movie does not have an imdb_rating yet (is None); don't show any suggestions.
            other_movies = ()
        else:
            other_movies = Movie.objects.select_related('parental_rating', 'genre').filter(
                bechdel_rating=3,
                imdb_rating__gt=float(movie.imdb_rating) - 1.5,
                parental_rating__id__lte=movie.parental_rating.id,
                ).exclude(id=movie.id)

            for genre in movie.genre.all()[:2 if len(movie.genre.all()) >= 2 else len(movie.genre.all())]:
                other_movies = other_movies.filter(genre__name=genre.name)

            sample_size = 10 if other_movies.count() >= 10 else other_movies.count()

            # Consider other ways of handling this as well, especially if sample size is too large

            # Get a random top 10
            context['other_movies'] = random.sample(other_movies, sample_size)

        return context

class AllMovies(TemplateView):

    def get(self, request, **kwargs):

        query = request.GET.get('q')
        genre = request.GET.get('g')
        decade = request.GET.get('d')
        letter = request.GET.get('l')
        parental = request.GET.get('p')

        context = self.get_context_data(**{'query': query,
            'genre': genre,
            'request': request,
            'decade': decade,
            'letter': letter,
            'parental': parental,
            })

        if context['showmessage']:
            messages.info(request, 'Showing {0} movies'.format(len(context['all_movies'])))

        return render(request, context['template_name'], context)

    def get_context_data(self, **kwargs):

        query = kwargs.get('query')
        genre_picked = kwargs.get('genre')
        decade_picked = kwargs.get('decade')
        letter_picked = kwargs.get('letter')
        parental_picked = kwargs.get('parental')

        all_movies = Movie.objects
        total_movies = Movie.objects.count()

        template_name = 'all.html'
        categories = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

        showmessage = False

        if letter_picked:
            if letter_picked in categories:
                all_movies = all_movies.filter(title__startswith=letter_picked).order_by('title', 'year')
                showmessage = True
            elif letter_picked == '0':
                for category in categories:
                    all_movies = all_movies.exclude(title__startswith=category).order_by('title', 'year')
                showmessage = True
            else:
                letter_picked = None

        if query:
            if query == 'genre':
                template_name = 'all_genre.html'
                categories = [genre.name for genre in Genre.objects.all().order_by('name')]
                categories.sort()
                try:
                    genre_picked = Genre.objects.get(name=genre_picked)
                except ObjectDoesNotExist:
                    genre_picked = None
                else:
                    all_movies = all_movies.filter(genre__name=genre_picked.name).order_by('title', 'year')
                    showmessage = True
            elif query == 'parental':
                template_name = 'all_parental.html'
                categories = [parent.rating for parent in ParentalRating.objects.all().order_by('id')]
                try:
                    parental_picked = ParentalRating.objects.get(rating=parental_picked)
                except ObjectDoesNotExist:
                    parental_picked = None
                else:
                    all_movies = all_movies.filter(parental_rating=parental_picked).order_by('title', 'year')
                    showmessage = True
            elif query == 'years':
                template_name = 'all_years.html'
                categories = ['2010', '2000', '1990', '1980', '1970', '1960', '1950', '1940', '1930', '1920', '1910', '1900', '1890']
                try:
                    decade_picked = int(decade_picked)
                except:
                    decade_picked = None
                else:
                    if decade_picked in [1890, 1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010]:
                        all_movies = [movie for movie in all_movies.iterator() if decade_picked + 10 > movie.year >= decade_picked]
                        showmessage = True
                    else:
                        decade_picked = None

        context = {
            'total_movies': total_movies,
            'all_movies': all_movies,
            'template_name': template_name,
            'categories': categories,
            'genre_picked': genre_picked,
            'decade_picked': decade_picked,
            'parental_picked': parental_picked,
            'letter_picked': letter_picked,
            'showmessage': showmessage,
        }

        return context

class WhatIsTheTestView(TemplateView):

    template_name = 'what.html'

    def get_context_data(self, **kwargs):
        total_movies = Movie.objects.count()
        context = {
            'total_movies': total_movies,
        }
        return context

class BechdelBotView(TemplateView):

    template_name = 'bot.html'

    def get(self, request, **kwargs):

        title = request.GET.get('t')

        context = self.get_context_data(**{
                'title': title,
            })

        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):

        title = kwargs.get('title')

        try:
            movie = Movie.objects.filter(title__icontains=title)
        except:
            context = {
                'items': -1,
                'search': title,
            }
        else:
            context = {
                'items': len(movie),
                'search': title,
            }

            if len(movie) == 0:
                pass
            elif len(movie) > 1:
                context.update({
                    'url': 'http://shannonvturner.com/bechdel/search?q={0}'.format(title),
                })
            else:
                movie = movie[0]

                context.update({
                        'title': movie.title,
                        'pass_fail': 'passed' if movie.bechdel_rating == 3 else 'failed',
                        'id': movie.id,
                    })

        import json
        context = {'json': json.dumps(context)}

        return context