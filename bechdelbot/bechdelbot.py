import time, sys
import requests
import tweepy

from bechdelbot_credentials import CONSUMER_KEY, CONSUMER_SECRET, \
    ACCESS_KEY, ACCESS_SECRET

auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
api = tweepy.API(auth)

print '''
-----START-----
{0}{1:02d}{2:02d}-{3:02d}{4:02d}{5:02d}
---------------'''.format(*time.localtime()[:6])

# Get ID of the most recent status (reply) the bot posted
try:
    with open('MOST_RECENT_BECHDELBOT.txt') as most_recent:
        most_recent = most_recent.read().strip()
except:
    print "[ERROR] Failed to open MOST_RECENT_BECHDELBOT.txt"
    print '---EARLY-END---'
    sys.exit()
else:
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

        print "\t", mention.id, mention.text

        if mention.id > new_most_recent:
            new_most_recent = mention.id

        # Check to see whether the mention was the name of a movie
        try:
            response = requests.get('http://shannonvturner.com/bechdel/bot?t={0}'.format(
                mention.text.lower().replace("@bechdelbot ", "").strip())).json()
        except:
            reply = False # fail silently
        else:

            items = response.get('items', -2)

            if items < 0:
                reply = False # fail silently
            elif items > 1:
                reply = '#bechdelbot found {0} movies that matched. choose one: {1}'.format(
                    items, response.get('url', ''))
            elif items == 1:

                reply = '''{0} {1} the #Bechdel test http://shannonvturner.com/bechdel/movie/{2}#s

                #bechdelbot'''.format(response.get('title', ''), 
                    response.get('pass_fail', ''), response.get('id', ''))

                if len(reply) > 140:
                    reply = '''http://shannonvturner.com/bechdel/movie/{0}#s

                    #bechdelbot'''.format(response.get('id', ''))

            if reply:
                try:
                    api.update_status(**{
                            'status': reply,
                            'in_reply_to_status_id': mention.id,
                        })
                except:
                    print "[ERROR] Failed to update_status (reply: {0})".format(mention.id)
                else:
                    print "[OK] Sent reply to {0}".format(mention.id)

    if new_most_recent:
        with open('MOST_RECENT_BECHDELBOT.txt', 'w') as most_recent:
            most_recent.write(str(new_most_recent))

    print '------END------'