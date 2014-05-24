from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F

from apps.bechdel.models import Movie, ParentalRating, Genre, Search

import requests

class HomeView(TemplateView):

    template_name = 'home.html'

    def get(self, request, **kwargs):

        context = {}

        return render(request, self.template_name, context)

class SearchView(TemplateView):

    ' Show choices when more than one movie has been returned for the query. '

    template_name = 'select.html'

    def post(self, request, **kwargs):

        query = request.POST.get('q')

        if not query:
            messages.error(request, 'Please enter your search.')
            return HttpResponseRedirect('/')
        else:
            if not ''.join([q for q in query if q.isalpha() or q.isdigit()]):
                # Eliminate other bad queries
                messages.error(request, 'Please enter your search.')
                return HttpResponseRedirect('/')

        query = query.replace("'", '&#39;')

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
        new_search = Search(search=query)
        new_search.save()

        try:
            bechdel_response = requests.get(bechdel_request_url).json()
        except:
            messages.error(request, 
                '''An error occurred while searching the Bechdel Test API for {0}.  
                Please try again.'''.format(query)
                )
            return HttpResponseRedirect('/')

        if direct_lookup:
            # Direct Lookup returns JSON, title search returns a list of items
            bechdel_response = [bechdel_response]

        if len(bechdel_response) == 0:
            messages.error(request, 
                '''The movie you searched for, {0}, was not found. 
                Either the movie does not exist in the Bechdel Test API database, 
                or your search was too complex.  Please try again.
                '''.format(query))
            return HttpResponseRedirect('/')
        else:
            # Loop through each response item, add to database
            for movie in bechdel_response:
                
                # Check to see whether it exists already in the database
                if movie.get('imdbid'):
                    try:
                        Movie.objects.get(imdb_id=movie['imdbid'])
                    except ObjectDoesNotExist:
                        # This movie is not yet in the database, so add it.
                        new_movie_details = {
                            'title': movie.get('title', '').replace('&#39;', "'"),
                            'year': movie.get('year'),
                            'bechdel_rating': movie.get('rating'),
                            'bechdel_disputed': movie.get('dubious'),
                            'imdb_id': movie.get('imdbid'),
                        }
                        new_movie = Movie(**new_movie_details)
                        new_movie.save()

        if len(bechdel_response) == 1:
            try:
                movie = Movie.objects.get(imdb_id=bechdel_response[0].get('imdbid'))
            except ObjectDoesNotExist:
                messages.error(request, 'An error occurred.  Please try your search again.')
                return HttpResponseRedirect('/')
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

            return render(request, self.template_name, context)

class MovieView(TemplateView):

    ' Show the summary page for one movie. '

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
            return HttpResponseRedirect('/')

        try:
            movie = Movie.objects.get(id=movie_id)
        except ObjectDoesNotExist:
            messages.error(request, 'Movie ID #{0} not found in our system, please try again.'.format(movie_id))
            return HttpResponseRedirect('/')

        # Request info from the OMDB API
        try:
            omdb_response = requests.get('http://www.omdbapi.com/?i={0}{1}&y={2}&tomatoes=true'.format('tt' if 'tt' not in movie.imdb_id[:2] else '', movie.imdb_id, movie.year)).json()
        except:
            # If the omdb request failed, that's okay -- continue with the information we do have
            pass
        else:
            # If any information is different, update it in the database.

            # "Genre":"Action, Comedy, Romance"
            omdb_response_genres = omdb_response.get('Genre', '').split(',')

            # if omdb_response_genres[0] != '':
            #     for omdb_response_genre in omdb_response_genres:
            #         if omdb_response_genre not in movie.genres:
            #             genre = Genre(name=omdb_response_genre, movie=movie)

            # OMDB Title should take precedence over Bechdel API Title
            if movie.title != omdb_response.get('Title') and omdb_response.get('Title'):
                movie.title = omdb_response.get('Title')

            if movie.parental_rating != omdb_response.get('Rated') and omdb_response.get('Rated'):
                try:
                    movie.parental_rating = ParentalRating.objects.get(rating=omdb_response.get('Rated'))
                except ObjectDoesNotExist:
                    pass

            if movie.runtime != omdb_response.get('Runtime') and omdb_response.get('Runtime'):
                # Assume minutes
                try:
                    movie.runtime = int(''.join([i for i in omdb_response.get('Runtime', '') if i.isdigit()]))
                except:
                    pass

            if movie.director != omdb_response.get('Director') and omdb_response.get('Director'):
                movie.director = omdb_response.get('Director')

            if movie.writer != omdb_response.get('Writer') and omdb_response.get('Writer'):
                movie.writer = omdb_response.get('Writer')

            if movie.actors != omdb_response.get('Actors') and omdb_response.get('Actors'):
                movie.actors = omdb_response.get('Actors')

            if movie.plot != omdb_response.get('Plot') and omdb_response.get('Plot'):
                movie.plot = omdb_response.get('Plot')

            if movie.country != omdb_response.get('Country') and omdb_response.get('Country'):
                movie.country = omdb_response.get('Country')

            if movie.awards != omdb_response.get('Awards') and omdb_response.get('Awards'):
                movie.awards = omdb_response.get('Awards')

            if movie.box_office_receipts != omdb_response.get('BoxOffice') and omdb_response.get('BoxOffice'):
                try:
                    omdb_response['BoxOffice'] = int(omdb_response['BoxOffice'].replace('$','').replace('M','00000').replace('.',''))
                except:
                    pass
                else:
                    if omdb_response['BoxOffice'] > 0:
                        movie.box_office_receipts = omdb_response['BoxOffice']

            if movie.imdb_rating != omdb_response.get('imdbRating') and omdb_response.get('imdbRating'):
                movie.imdb_rating = omdb_response.get('imdbRating')

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
            '''{0} has a Bechdel rating of {1}/3. That means {2} {3}'''.format(
                movie.title, movie.bechdel_rating, 
                self.bechdel_rating_explanations[str(movie.bechdel_rating)][1],
                self.bechdel_dispute_explanation['disputed'] if movie.bechdel_disputed else self.bechdel_dispute_explanation['undisputed']
                )
            )

        context = {
            'movie': movie
        }

        if movie.bechdel_rating == 3:
            context['title'] = "Other movies you may enjoy"
        else:
            context['title'] = "Watch these instead"

        other_movies = Movie.objects.filter(
            bechdel_rating=3,
            imdb_rating__gt=float(movie.imdb_rating) - 1.5,
            parental_rating__id__lte=movie.parental_rating.id,
            )

        # TODO
        # If current movie has 1 genre: match the genre
        # If current movie has 2+ genres: match 2 genres
        # for genre in movie.genres[:2 if len(movie.genres) >= 2 else len(movie.genres)]:
        #     other_movies.filter(genres__contains=genre)

        context['other_movies'] = list(other_movies)

        return render(request, self.template_name, context)