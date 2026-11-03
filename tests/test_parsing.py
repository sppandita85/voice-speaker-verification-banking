from datetime import date

from app.dialog.parsing import parse_card_choice, parse_mobile, parse_step_up, spoken_digits
from app.speech.speakable import number_to_words, ordinal_words, to_speech


def test_mobile_from_digits_and_words():
    assert parse_mobile("My number is 050 100 0001") == "971501000001"
    assert parse_mobile("+971 50 100 0001") == "971501000001"
    assert parse_mobile("zero five zero one double zero, zero zero zero one") == "971501000001"
    assert parse_mobile("I don't know") is None


def test_spoken_digits_triple():
    assert spoken_digits("triple five 6") == "5556"


def test_step_up_answer():
    assert parse_step_up("The last four digits are 5506 and my date of birth is 24 January 1972") == (
        "5506", date(1972, 1, 24))
    assert parse_step_up("5506, 24/01/1972") == ("5506", date(1972, 1, 24))
    assert parse_step_up("January 24th, 1972") == (None, date(1972, 1, 24))
    assert parse_step_up("five five zero six") == ("5506", None)


def test_card_choice():
    assert parse_card_choice("the one ending 1520", ["2679", "1520"]) == "1520"
    assert parse_card_choice("the first one", ["2679", "1520"]) == "2679"
    assert parse_card_choice("not sure", ["2679", "1520"]) is None


def test_speech_text():
    assert number_to_words(4250) == "four thousand two hundred and fifty"
    assert number_to_words(1005) == "one thousand and five"
    assert ordinal_words(25) == "twenty-fifth"
    assert ordinal_words(30) == "thirtieth"
    spoken = to_speech("Your card ending 5506 owes AED 4,250.75, due on 25 November.")
    assert spoken == ("Your card ending five five zero six owes four thousand two hundred and fifty dirhams "
                      "and seventy-five fils, due on the twenty-fifth of November.")
