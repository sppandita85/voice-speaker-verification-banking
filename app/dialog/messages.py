"""Fixed bot phrases, keyed by language. Add an "ar" block here to support Arabic."""

MESSAGES = {
    "en": {
        "greet_identify": "Welcome to Demo Bank. To get started, please say your registered mobile number.",
        "greet_known": "Welcome to Demo Bank. In a sentence or two, please tell me how I can help you today.",
        "mobile_not_found": "Sorry, I couldn't find that number. Please say your registered mobile number again, digit by digit.",
        "didnt_catch": "Sorry, I didn't catch that. Could you say it again?",
        "too_short": "I need to hear a little more of your voice. Please tell me, in a full sentence, how I can help.",
        "step_up": "For your security, please tell me the last 4 digits of your card and your date of birth.",
        "step_up_need_last4": "Thank you. Now please tell me the last 4 digits of your card.",
        "step_up_need_dob": "Thank you. Now please tell me your date of birth.",
        "voice_retry": "Sorry, I couldn't verify your voice. Please tell me again, in a full sentence, how I can help, or say agent to speak to a colleague.",
        "step_up_retry": "Sorry, those details don't match our records. Please try again, or say agent to speak to a colleague.",
        "verified_ask": "Thank you, you're verified. How can I help you today?",
        "pick_card": "You have {count} cards, ending {cards}. Which card would you like?",
        "pick_card_retry": "Sorry, which card? Please say the last 4 digits, for example {example}.",
        "anything_else": "Is there anything else I can help with?",
        "out_of_scope": "I can help with your card balance and payment due date. For anything else, I can transfer you to a colleague. Would you like that?",
        "no_transfer": "No problem.",
        "nothing_to_repeat": "Sorry, how can I help you?",
        "handover": "I'm transferring you to a colleague now. Your reference is {reason}. Please hold.",
        "locked": "For your security, I can't continue verification on this call. I'm transferring you to a colleague. Your reference is {reason}.",
        "goodbye": "Thank you for calling Demo Bank. Goodbye.",
        "call_ended": "This call has ended. Please start a new call.",
        "and": "and",
    },
}


def msg(language: str, key: str, **kwargs) -> str:
    return MESSAGES[language][key].format(**kwargs)
