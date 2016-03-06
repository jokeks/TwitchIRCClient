import twitch_irc
from message_reciver import event_handler

CHANNEL = "#SOMECHANNEL"
USERNAME = "SOMEUSERNAME"
PASSWORD = "oauth:somepassword"

client = twitch_irc.TwitchClient(channel=CHANNEL, username=USERNAME, password=PASSWORD)
event_h = event_handler()

client.register_event_type('on_message')
client.register_event_type('on_join')

client.push_handlers(event_handler.on_message, event_handler.on_join)

# Start twitch chlient thread
client.start()

while True:
    # Do some shit
    pass
