# Use this to activate virtualenv on the server.
import os, sys, site

# Tell wsgi to add the Python site-packages to its path. 
site.addsitedir('/home/sturner/.virtualenvs/bechdel/lib/python2.7/site-packages')

activate_this = os.path.expanduser("~/.virtualenvs/bechdel/bin/activate_this.py")
execfile(activate_this, dict(__file__=activate_this))

# Calculate the path based on the location of the WSGI script
project = '/home/sturner/webapps/bechdel/bechdel/'
workspace = os.path.dirname(project)
sys.path.append(workspace)

########

import random
import time
import requests
import tweepy

from bechdelbot_credentials import CONSUMER_KEY, CONSUMER_SECRET, \
    ACCESS_KEY, ACCESS_SECRET

auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
api = tweepy.API(auth)

fullpath = "{0}bechdelbot/".format(project)

BECHDELBOT_TWITTER_ID = 2712977612

print '''
-----START-----
{0}{1:02d}{2:02d}-{3:02d}{4:02d}{5:02d}
---------------'''.format(*time.localtime()[:6])

# Get ID of the most recent status (reply) the bot posted
try:
    with open('{0}MOST_RECENT_BECHDELBOT.txt'.format(fullpath)) as most_recent:
        most_recent = most_recent.read().strip()
    with open('{0}BECHDELBOT_FOLLOWS.txt'.format(fullpath)) as follows:
        follows = follows.read().strip().split("\n")
except Exception:
    print "[ERROR] Failed to open MOST_RECENT_BECHDELBOT.txt or ..._FOLLOWS.txt"
    print '---EARLY-END---'
    sys.exit()
else:

    # ################################################################# #
    # SECTION 1:
    # SEARCH FOR USERS WHO TWEET ABOUT THE BECHDEL TEST AND FOLLOW THEM
    # ################################################################# #
    print "[INFO] Searching for users tweeting about the Bechdel test."

    search_items = (
        'bechdel test',
        'bechdel',
        'bechdeltest',
        '#bechdeltest',
        '#bechdel',
    )

    already_added = list(follows)

    for search_item in search_items:
        try:
            time.sleep(.5)
            found_users = api.search(**{
                'q': search_item,
                'rpp': 100,
                })
        except Exception:
            print "\t[ERROR] Failed to search for users tweeting about the Bechdel test"
        else:
            for found_user in found_users:
                if str(found_user.author.id) in already_added:
                    # Skip if user has already been followed
                    continue

                try:
                    time.sleep(.5)
                    api.create_friendship(id=found_user.author.id)
                except Exception:
                    print "\t[ERROR] Failed to add id #", found_user.author.id
                else:
                    pass
                finally:
                    already_added.append("{0}".format(found_user.author.id))

    with open('{0}BECHDELBOT_FOLLOWS.txt'.format(fullpath), 'w') as follows_file:
        follows_file.write('\n'.join(already_added))

    # ################################################ #
    # END OF SECTION 1 (FOLLOW NEW USERS)
    # ################################################ #

    # ################################################ #
    # SECTION 2:
    # UNFOLLOW NON-MUTUAL FOLLOWS TO AVOID FOLLOW CAP
    # ################################################ #

    # Current setting: unfollow roughly 15 times per day (2% of the time)
    should_i_unfollow = random.randint(1, 100)

    if should_i_unfollow >= 99:
        # Unfollow oldest first.
        # Unfollow 7-13 at a time
        unfollow_this_many = random.randint(7, 13)

        # Just a plain list of integers (IDs of the people the bot follows)
        my_follows = api.friends_ids(id=BECHDELBOT_TWITTER_ID)
        my_follows.reverse()

        # IDs of the people following the bot
        my_followers = api.followers_ids(id=BECHDELBOT_TWITTER_ID)

        # Subtract people following me from those I'm following
        # Keep only 7-13
        people_to_unfollow = list(set(my_follows) - set(my_followers))[:unfollow_this_many]

        assert 7 <= len(people_to_unfollow) <= 13

        for person_to_unfollow in people_to_unfollow:
            try:
                api.destroy_friendship(id=person_to_unfollow)
            except Exception:
                print "[ERROR] Failed to unfollow ", person_to_unfollow
            else:
                print "[OK] Unfollowed ", person_to_unfollow
    else:
        print "[INFO] Not unfollowing this time."

    # ################################################ #
    # END OF SECTION 2 (UNFOLLOW TO AVOID FOLLOW CAP)
    # ################################################ #

    # ################################################ #
    # SECTION 3:
    # CHECK FOR @ MENTIONS AND REPLY DIRECTLY TO USERS
    # ################################################ #
    if most_recent:
        mentions = api.mentions_timeline(since_id=most_recent)
    else:
        mentions = ()

    # print "mentions: ", mentions

    if len(mentions) == 0:
        print "[INFO] Zero mentions; no need to update."
        print '---EARLY-END---'
        sys.exit()
    else:
        print "[INFO] MENTIONS SINCE LAST UPDATE: {0}".format(len(mentions))

    new_most_recent = int(most_recent)

    for mention in mentions:

        if mention.id > new_most_recent:
            new_most_recent = mention.id

        # Check to see whether the mention was the name of a movie
        try:
            response = requests.get('http://shannonvturner.com/bechdel/bot?t={0}'.format(
                mention.text.lower().replace("@bechdelbot ", "").strip())).json()
        except Exception:
            reply = False  # fail silently
        else:

            items = response.get('items', -2)

            if items <= 0:
                reply = False
            elif items > 1:
                reply = '@{0} #bechdelbot found {1} movies that matched. choose one: {2}'.format(
                    mention.author.screen_name, items, response.get('url', ''))
            elif items == 1:

                reply = '''@{0} {1} {2} the #Bechdel test http://shannonvturner.com/bechdel/movie/{3}#s\n\n#bechdelbot'''.format(
                    mention.author.screen_name, response.get('title', ''), response.get('pass_fail', ''), response.get('id', ''))

                if len(reply) > 140:
                    reply = '''@{0} http://shannonvturner.com/bechdel/movie/{1}#s\n\n#bechdelbot'''.format(
                        mention.author.screen_name, response.get('id', ''))

            if reply:
                try:
                    api.update_status(**{
                            'status': reply,
                            'in_reply_to_status_id': mention.id,
                        })
                except Exception:
                    print "\t[ERROR] Failed to update_status (reply: {0})".format(mention.id)
                else:
                    print "\t[OK] Sent reply to {0}".format(mention.id)

    if new_most_recent:
        with open('{0}MOST_RECENT_BECHDELBOT.txt'.format(fullpath), 'w') as most_recent:
            most_recent.write(str(new_most_recent))

    # ################################################ #
    # END OF SECTION 3 (REPLY TO MENTIONS)
    # ################################################ #

    print '------END------'