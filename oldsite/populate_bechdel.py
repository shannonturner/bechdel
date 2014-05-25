import bechdel
import requests
import time

" Pre-populate database with everything currently in the Bechdel Test API "

endpoint = 'http://bechdeltest.com/api/v1/getAllMovieIds'
response = requests.get(endpoint).json()

print len(response), " movies to cycle through."

for movie in response:

    time.sleep(1)

    print "Now on ", movie['imdbid']

    try:

        # Bechdel Results
        movie_response = requests.get('http://bechdeltest.com/api/v1/getMovieByImdbId?imdbid={0}'.format(movie['imdbid'])).json()

        if 'tt' not in movie_response['imdbid']:
            movie_response['imdbid'] = 'tt{0}'.format(movie_response['imdbid'])
                                                      
        bechdel.update_database(movie_response)

        # OMDB / Tomato Results
        omdb_response = requests.get('http://www.omdbapi.com/?i={0}&y={1}&tomatoes=true'.format(movie['imdbid'], movie_response['year'])).json()
        bechdel.update_database(omdb_response)

    except Exception, e:
        print "[ERROR] Failed on ", e, " continuing ..."
                                 
