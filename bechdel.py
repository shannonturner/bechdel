#!/usr/local/bin/python2.7

import bechdel_credentials
import cherrypy
import psycopg2
import requests

class Root(object):

    @cherrypy.expose
    def index(self, **kwargs):

        """ index(): Search page for movies.
        """

        search = kwargs.get('search', '')
        del kwargs

        if search == '':
            return wrap_in_css('')

        if search.isdigit():
            bechdel_request_url = 'http://bechdeltest.com/api/v1/getMovieByImdbId?imdbid={0}'.format(search)
        else:
            if search[0:2] == 'tt':
                bechdel_request_url = 'http://bechdeltest.com/api/v1/getMovieByImdbId?imdbid={0}'.format(search)
            else:
                if search[0:4].lower() == 'the ':
                    search = "{0}, {1}".format(search[4:], search[0:3]) # Changes The Matrix (which doesn't work) to Matrix, The (which does)
                bechdel_request_url = 'http://bechdeltest.com/api/v1/getMoviesByTitle?title={0}'.format(search.replace(' ', '+'))
                
        try:
            bechdel_response = requests.get(bechdel_request_url).json()
        except requests.ConnectionError:
            error_message = {'message': 'Failed to get requested information from the Bechdel Test API'}
            self.error(**error_message)

        if len(bechdel_response) == 0:
            return wrap_in_css('<i>Sorry, we weren\'t able to find: {0}</i><br>Try a different search!'.format(search))

        if len(bechdel_response) > 1:

            page_source = []           

            table_source = []
            
            for response in bechdel_response:

                if 'tt' not in response['imdbid']:
                    response['imdbid'] = 'tt{0}'.format(response['imdbid'])

                if response['rating'] == '3':
                    rating_color = '#a3edb9'
                elif response['rating'] == '2':
                    rating_color = '#ffffc0'
                elif response['rating'] == '1':
                    rating_color = '#ff8080'
                else:
                    rating_color = ''
                
                table_source.append('<table cellpadding=4 style="vertical-align: middle; text-align: center;">')
                table_source.append('<tr><td><b><a href="rating?imdbid={0}&year={1}&rating={2}&dubious={3}&title={4}">{4} ({1})</a></b></td></tr>'.format(response['imdbid'], response['year'], response['rating'], response['dubious'], response['title']))
                table_source.append('<tr><td style="background-color:{0}">Bechdel Rating: {1}</td></tr>'.format(rating_color, response['rating']))
                table_source.append('</table><br>')

                update_database(response)

            page_source.append('<i>{0} results returned for {1}.</i><br>'.format(len(bechdel_response), search))
            page_source.extend(table_source)

            return wrap_in_css(page_source)

        if len(bechdel_response) == 1:

            bechdel_response = bechdel_response.pop()
            
            if 'tt' not in bechdel_response['imdbid']:
                bechdel_response['imdbid'] = 'tt{0}'.format(bechdel_response['imdbid'])

            update_database(bechdel_response)

            return self.rating(**bechdel_response)

    @cherrypy.expose
    def rating(self, **bechdel_response):

        """ rating(): Rating page for movies.
        """
        
        bechdel = {}
        bechdel['imdbid'] = bechdel_response.get('imdbid')
        bechdel['rating'] = int(bechdel_response.get('rating', -1))
        bechdel['dubious'] = int(bool(bechdel_response.get('dubious', -1))) if bechdel_response.get('dubious') is not None else 0
        bechdel['title'] = bechdel_response.get('title')
        bechdel['year'] = bechdel_response.get('year')

        if bechdel['imdbid'] is None or bechdel['rating'] is -1:
            error_message = {'message': 'No IMDB ID given or Rating not found.  Please try your search again.'}
            self.error(**error_message)

        # Get the tomato rating, too.
        omdb_request_url = 'http://www.omdbapi.com/?i={0}&y={1}&tomatoes=true'.format(bechdel['imdbid'], bechdel['year'])
        try:
            omdb_response = requests.get(omdb_request_url).json()
        except requests.ConnectionError:
            error_message = {'message': 'Failed to get requested information from the OMDB API'}
            self.error(**error_message)

        if omdb_response.has_key('Error'):
            error_message = {'message': "{0}: {1}".format(omdb_response['Error'], bechdel['imdbid'])}
            return self.error(**error_message)
        
        update_database(omdb_response)

        database_connection = psycopg2.connect(bechdel_credentials.database_connection_details)
        database_cursor = database_connection.cursor()

        ## For rating == 3, show stats about average ratings
        
        if bechdel['rating'] == 3 and bechdel['dubious'] == 0:

            return wrap_in_css('Great news! <b><u>{0}</u></b> has a Bechdel rating of 3! <br> That means at least two women are in the movie, and they talk to one another about something other than a man! Baby steps, Hollywood. <br> Enjoy your film. <br>'.format(bechdel['title']))

        elif bechdel['rating'] == 3 and bechdel['dubious'] == 1:

            return wrap_in_css('Good news! <b><u>{0}</u></b> has a Bechdel rating of 3! <br> That means at least two women are in the movie, and they talk to one another about something other than a man!  However, the rating for this film is somewhat disputed.'.format(bechdel['title']))

        else:

            page_source = []

            # Show the full details as returned by API
            details_table = []
            details_table.append('<table cellpadding=4 style="text-align: center; vertical-align: middle;"><tr><td colspan=3><h3>{0} ({1})</h3></td></tr>'.format(omdb_response['Title'], omdb_response['Year']))
            details_table.append('<tr> <td>Rated: {0}</td> <td>Runtime: {1}</td> <td>Genre: {2}</td>'.format(omdb_response['Rated'], omdb_response['Runtime'], omdb_response['Genre']))
            details_table.append('<tr> <td colspan=3> <i> {0} </i> </td> </tr>'.format(omdb_response['Plot']))
            details_table.append('</table><br> <br>')           

            # Search the database for a film with a higher Bechdel and higher tomato meter
            higher_table = []
            higher_table.append('<table cellpadding=4 style="text-align: center; vertical-align: middle;"><tr><td colspan=5><b>Here are some other movies in the same genre with higher Bechdel, IMDB, and Rotten Tomato scores.</b></td></tr>')
            higher_table.append('<tr> <td><b>Movie</b></td> <td>Bechdel Score</td> <td>IMDB Rating</td> <td>Rotten Tomatoes Rating</td> <td>Genre</td> </tr>')

            higher_query = "select imdb_id, title, bechdel_rating, imdb_rating, tomato_meter, genre from movies where bechdel_rating > {0} and imdb_rating > {1} and tomato_meter > {2} and (id = -1 {3}) order by bechdel_rating desc, imdb_rating desc, tomato_meter desc limit 25".format(bechdel['rating'], omdb_response['imdbRating'], omdb_response['tomatoMeter'], ''.join([" or genre like '%{0}%'".format(x) for x in omdb_response['Genre'].split(', ')]))
            database_cursor.execute(higher_query)
            for higher_rated in database_cursor.fetchall():
                higher_table.append('<tr> <td><a href="index?search={0}><b>{1}</b></a></td> <td>{2}</td> <td>{3}</td> <td>{4}</td> <td>{5}</td> </tr>'.format(*higher_rated))

            higher_table.append('</table><br> <br>')

            # Show the Bechdel & other ratings for this film
            average_table = []
            average_table.append('<table cellpadding=4 style="text-align: center; vertical-align: middle;"><tr><td colspan=3><h3>This Movie\'s Scores</h3></td></tr>')
            average_table.append('<tr> <td>Bechdel Score</td> <td>IMDB Rating</td> <td>Rotten Tomatoes Rating</td> </tr>')
            
            average_table.append('<tr> <td> {0} / 3 </td> <td> {1} </td> <td> {2} </td> </tr>'.format(bechdel['rating'], omdb_response['imdbRating'], omdb_response['tomatoMeter']))

            average_table.append('<tr> <td colspan=3> </td> </tr>')
            average_table.append('<tr><td colspan=3><b>Average Scores for All Movies Currently in the Database</b></td></tr>')

            average_all_query = "select avg(bechdel_rating), avg(imdb_rating), avg(tomato_meter) from movies"
            database_cursor.execute(average_all_query)
            for average_all in database_cursor.fetchall():
                average_table.append('<tr> <td> {0:.0f} / 3 </td> <td> {1:.0f} </td> <td> {2:.0f} </td> </tr>'.format(*average_all))

            average_table.append('<tr> <td colspan=3> </td> </tr>')
            average_table.append('<tr> <td colspan=3> <b> Average Scores for All Movies with a Bechdel Rating of {0} Currently in the Database </b> </td> </tr>'.format(bechdel['rating']))
            
            average_this_rating_query = '{0} where bechdel_rating = {1}'.format(average_all_query, bechdel['rating'])
            database_cursor.execute(average_this_rating_query)
            for average_all in database_cursor.fetchall():
                average_table.append('<tr> <td> {0:.0f} / 3 </td> <td> {1:.0f} </td> <td> {2:.0f} </td> </tr>'.format(*average_all))

            average_table.append('</table>')

            page_source.extend(details_table)
            page_source.extend(higher_table)
            page_source.extend(average_table)

            return wrap_in_css(page_source)

    @cherrypy.expose
    def error(self, **kwargs):

        """ error(): Catch-all error page.
        """

        message = kwargs.get('message')
        del kwargs

        return wrap_in_css('Something went wrong.  Sorry. <br> Details: {0}'.format(message))


def wrap_in_css(source):

    """ wrap_in_css(source): Wraps the provided source in formatting and necessary API data disclosures.
    """

    page_source = []

    page_source.append('<p><h2 style="text-align: center;">The Bechdel-Tomato-Movie Database</h2></p>')

    page_source.extend(source)

    page_source.append('<br> <br> <form method=post action=index>Search for a movie by title or IMDB ID: <input type=text name=search><input type=submit value=Go></form> <br> <br> <hr width=50%> <br> <i>All data provided by <a href="http://bechdeltest.com/api/" target="_blank">The Bechdel Test API</a> and <a href="http://omdbapi.com/" target="_blank">The Open Movie Database API</a> (which includes data from <a href="http://www.rottentomatoes.com/" target="_blank">Rotten Tomatoes</a>)</i>')
    page_source.append('<br> <i> This webpage is open-source.  Check out the code and submit feature requests and bugs here: <a href="https://github.com/shannonturner/bechdel" target="_blank">https://github.com/shannonturner/bechdel</a> </i> ')

    return page_source
        
def update_database(data):

    """ update_database(data): Updates the database with the retrieved movie data.
    """
    
    database_connection = psycopg2.connect(bechdel_credentials.database_connection_details)
    database_cursor = database_connection.cursor()

    check_existing_query = "select id, imdb_id, bechdel_rating, bechdel_dispute, year, title, rated, imdb_rating, tomato_meter, tomato_fresh, tomato_rotten, tomato_user_meter, tomato_user_rating, box_office, production, genre from movies where imdb_id = '{0}'".format(data['imdbid'] if data.has_key('imdbid') else data['imdbID'])

    try:
        database_cursor.execute(check_existing_query)
        check_existing = database_cursor.fetchone()
    except AttributeError, e:
        if "'NoneType' object has no attribute 'fetchone'" in e:
            existing = False
    else:
        existing = True

    if check_existing is None:
        existing = False

    if data.has_key('dubious'):
        # This is the Bechdel set of returns

        if existing:
            if None in check_existing[2:6]:
                make_updates = {}
                if data.get('imdbid') is not None and check_existing[1] is None:
                    make_updates['imdb_id'] = data.get('imdbid')
                if data.get('rating') is not None and check_existing[2] is None:
                    make_updates['bechdel_rating'] = data.get('rating')
                if data.get('dubious') is not None and check_existing[3] is None:
                    make_updates['bechdel_dispute'] = data.get('dubious', 0)
                if data.get('year') is not None and check_existing[4] is None:
                    make_updates['year'] = data.get('year')

                if make_updates != {}:
                    update_query = "update movies set {0} where id = {1}".format(', '.join(["{0} = '{1}'".format(k, v) for k,v in make_updates.iteritems()]), check_existing[0])
                    database_cursor.execute(update_query)
                    database_connection.commit()
        else:            
            insert_query = "insert into movies (imdb_id, bechdel_rating, bechdel_dispute, year) values ('{0}', '{1}', '{2}', '{3}')".format(data.get('imdbid'), data.get('rating'), data.get('dubious') if data.get('dubious') is not None else 0, data.get('year'))
            database_cursor.execute(insert_query)
            database_connection.commit()

    elif data.has_key('Rated'):
        # This is the OMDB set of returns

        if existing:
            if None in check_existing[6:]:
                make_updates = {}
                if data.get('Title') is not None and check_existing[5] is None:
                    make_updates['title'] = data.get('Title')
                if data.get('Rated') is not None and check_existing[6] is None:
                    make_updates['rated'] = data.get('Rated')
                if data.get('imdbRating') is not None and check_existing[7] is None:
                    make_updates['imdb_rating'] = data.get('imdbRating')
                if data.get('tomatoMeter') is not None and data.get('tomatoMeter') != 'N/A' and check_existing[8] is None:
                    make_updates['tomato_meter'] = data.get('tomatoMeter')
                if data.get('tomatoFresh') is not None and data.get('tomatoFresh') != 'N/A' and check_existing[9] is None:
                    make_updates['tomato_fresh'] = data.get('tomatoFresh')
                if data.get('tomatoRotten') is not None and data.get('tomatoRotten') != 'N/A' and check_existing[10] is None:
                    make_updates['tomato_rotten'] = data.get('tomatoRotten')
                if data.get('tomatoUserMeter') is not None and data.get('tomatoUserMeter') != 'N/A' and check_existing[11] is None:
                    make_updates['tomato_user_meter'] = data.get('tomatoUserMeter')
                if data.get('tomatoUserRating') is not None and data.get('tomatoUserRating') != 'N/A' and check_existing[12] is None:
                    make_updates['tomato_user_rating'] = data.get('tomatoUserRating')
                if data.get('BoxOffice') is not None and check_existing[13] is None:
                    make_updates['box_office'] = int(str(data.get('BoxOffice')).replace('N/A', '0').replace('$','').replace('M','00000').replace('.',''))
                if data.get('Production') is not None and check_existing[14] is None:
                    make_updates['production'] = data.get('Production')
                if data.get('Genre') is not None and check_existing[15] is None:
                    make_updates['genre']= data.get('Genre')

                if make_updates != {}:
                    update_query = "update movies set {0} where id = {1}".format(', '.join(["{0} = '{1}'".format(k, v) for k,v in make_updates.iteritems()]), check_existing[0])
                    database_cursor.execute(update_query)
                    database_connection.commit()
                    
    database_connection.close()

    return

if __name__ == "__main__":

    configuration_file = 'cfg.cfg'

    cherrypy.root = Root()
    cherrypy.config.update({'error_page.default': cherrypy.root.error})
    cherrypy.quickstart(cherrypy.root, '/', configuration_file)    
