class Emoji:
    CURRY = '<:Curry:689531071217270878>'


def user_mention(user_id):
    return f'<@!{user_id}>'


def emoji_prefixed_message(emoji, message):
    return f'{emoji} {message}'


def curry_message(message):
    return emoji_prefixed_message(Emoji.CURRY, message)
