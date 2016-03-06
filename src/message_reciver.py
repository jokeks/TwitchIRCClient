class event_handler(object):
    @staticmethod
    def on_message(connection, message):
        """
        :type connection: twitchIRC.TwitchClient
        :type message: twitchIRC.Message
        """

        if message.message.lower() == "!respond":
            connection.send_chat("Respond to:".format(str(message)))

    @staticmethod
    def on_join(connection, channel, user):
        """
        :type connection: twitchIRC.TwitchClient
        :type channel: str
        :type user : str
        """
        answer = 'Hello @{user}, nice to meet you!'
        answer = answer.format(user=user)
        connection.send_chat(answer)
