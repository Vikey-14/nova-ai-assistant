import datetime
import calendar
import re
from difflib import get_close_matches

def fuzzy_match_any(command: str, phrase_list: list[str], cutoff=0.7) -> bool:
    matches = get_close_matches(command, phrase_list, n=1, cutoff=cutoff)
    return len(matches) > 0

def handle_date_queries(command: str) -> None:
    command = command.lower()

    from utils import _speak_multilang, logger

    # Phrases for date/time/month queries
    date_phrases = [
        "what is the date", "what day is it", "what day is today", "what's the date today", "today's date",
        "what is the time", "current time", "time now", "what month is it", "which month is it",
        "आज तारीख क्या है", "आज कौन सा दिन है", "तारीख बताओ", "समय क्या है", "वर्तमान समय", "समय अभी क्या है",
        "कौन सा महीना है", "महीना कौन सा है",
        "quelle est la date", "quel jour sommes-nous", "quelle est la date aujourd'hui", "quelle heure est-il",
        "quel mois sommes-nous", "quel est le mois",
        "cuál es la fecha", "qué día es hoy", "cuál es la fecha hoy", "qué hora es",
        "qué mes es", "cuál es el mes",
        "was ist das datum", "welcher tag ist heute", "was ist das heutige datum", "wie spät ist es",
        "welcher monat ist es", "was ist der monat"
    ]

    if fuzzy_match_any(command, date_phrases):
        now = datetime.datetime.now()
        weekday = calendar.day_name[now.weekday()]
        date_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%H:%M")
        month_name = now.strftime("%B")

        if fuzzy_match_any(command, ["time", "समय", "heure", "hora", "uhr"]):
            response = f"The current time is {time_str}."
            logger.info(f"Date Query (Time): Command='{command}', Response='{response}'")
            _speak_multilang(
                response,
                hi=f"वर्तमान समय है {time_str}।",
                fr=f"L'heure actuelle est {time_str}.",
                es=f"La hora actual es {time_str}.",
                de=f"Die aktuelle Uhrzeit ist {time_str}."
            )
            return

        elif fuzzy_match_any(command, ["month", "महीना", "mois", "mes", "monat"]):
            response = f"The current month is {month_name}."
            logger.info(f"Date Query (Month): Command='{command}', Response='{response}'")
            _speak_multilang(
                response,
                hi=f"वर्तमान महीना {month_name} है।",
                fr=f"Le mois en cours est {month_name}.",
                es=f"El mes actual es {month_name}.",
                de=f"Der aktuelle Monat ist {month_name}."
            )
            return

        else:
            response = f"Today is {weekday}, {date_str}."
            logger.info(f"Date Query (Date): Command='{command}', Response='{response}'")
            _speak_multilang(
                response,
                hi=f"आज {weekday} है, तारीख {date_str} है।",
                fr=f"Aujourd'hui, c'est {weekday}, le {date_str}.",
                es=f"Hoy es {weekday}, {date_str}.",
                de=f"Heute ist {weekday}, der {date_str}."
            )
            return

    # Leap year queries 
    leap_phrases = [
        "is this year a leap year", "when is the next leap year", "which year is a leap year",
        "when was the last leap year",
        "क्या यह वर्ष लीप वर्ष है", "अगला लीप वर्ष कब है", "पिछला लीप वर्ष कब था",
        "est-ce que c'est une année bissextile", "quand est la prochaine année bissextile", "quelle était la dernière année bissextile",
        "es este año bisiesto", "cuándo es el próximo año bisiesto", "cuándo fue el último año bisiesto",
        "ist dieses jahr ein schaltjahr", "wann ist das nächste schaltjahr", "wann war das letzte schaltjahr"
    ]

    if fuzzy_match_any(command, leap_phrases):
        year = datetime.datetime.now().year
        if fuzzy_match_any(command, ["next leap year", "अगला लीप वर्ष", "prochaine année bissextile", "próximo año bisiesto", "nächste schaltjahr"]):
            next_leap = year + (4 - year % 4)
            response = f"The next leap year is {next_leap}."
            logger.info(f"Leap Year Query (Next): Command='{command}', Response='{response}'")
        elif fuzzy_match_any(command, ["last leap year", "पिछला लीप वर्ष", "dernière année bissextile", "último año bisiesto", "letztes schaltjahr"]):
            last_leap = year - ((year - 1) % 4) - 4
            response = f"The last leap year was {last_leap}."
            logger.info(f"Leap Year Query (Last): Command='{command}', Response='{response}'")
        else:
            is_leap = calendar.isleap(year)
            response = f"This year {year} is " + ("a leap year." if is_leap else "not a leap year.")
            logger.info(f"Leap Year Query (Current): Command='{command}', Response='{response}'")
        _speak_multilang(
            response,
            hi=f"यह वर्ष {year} {'लीप वर्ष है।' if calendar.isleap(year) else 'लीप वर्ष नहीं है।'}",
            fr=f"Cette année {year} est {'bissextile.' if calendar.isleap(year) else 'pas bissextile.'}",
            es=f"Este año {year} {'es bisiesto.' if calendar.isleap(year) else 'no es bisiesto.'}",
            de=f"Dieses Jahr {year} ist {'ein Schaltjahr.' if calendar.isleap(year) else 'kein Schaltjahr.'}"
        )
        return

    # Specific past/future date queries: "what day was january 26, 1880"
    date_regex = r"(?:what|which) day (?:was|is) (\d{1,2}) ?(?:st|nd|rd|th)? ?([a-zA-Z]+) ?,? ?(\d{4})"
    match = re.search(date_regex, command)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)
        year = int(match.group(3))

        try:
            month = datetime.datetime.strptime(month_str, "%B").month
        except ValueError:
            try:
                month = datetime.datetime.strptime(month_str, "%b").month
            except ValueError:
                logger.error(f"Date Query: Invalid month name '{month_str}' in command '{command}'")
                _speak_multilang(
                    "Sorry, I couldn't understand the month you mentioned.",
                    hi="माफ़ करें, मैं जिस महीने का आप उल्लेख कर रहे हैं उसे समझ नहीं पाया।",
                    fr="Désolé, je n'ai pas compris le mois que vous avez mentionné.",
                    es="Lo siento, no entendí el mes que mencionaste.",
                    de="Entschuldigung, ich habe den von Ihnen genannten Monat nicht verstanden."
                )
                return

        try:
            date_obj = datetime.date(year, month, day)
            weekday = calendar.day_name[date_obj.weekday()]
        except ValueError:
            logger.error(f"Date Query: Invalid date {day}-{month}-{year} in command '{command}'")
            _speak_multilang(
                "That date is invalid. Please check and try again.",
                hi="यह तारीख अमान्य है। कृपया जांचें और पुनः प्रयास करें।",
                fr="Cette date est invalide. Veuillez vérifier et réessayer.",
                es="Esa fecha no es válida. Por favor, verifique e intente de nuevo.",
                de="Dieses Datum ist ungültig. Bitte überprüfen Sie es und versuchen Sie es erneut."
            )
            return

        response = f"{month_str.capitalize()} {day}, {year} was a {weekday}."
        logger.info(f"Date Query: Responding to '{command}' with '{response}'")
        _speak_multilang(
            response,
            hi=f"{year} का {month_str.capitalize()} {day} दिन {weekday} था।",
            fr=f"Le {day} {month_str.capitalize()} {year} était un {weekday}.",
            es=f"El {day} de {month_str.capitalize()} de {year} fue un {weekday}.",
            de=f"Der {day}. {month_str.capitalize()} {year} war ein {weekday}."
        )
        return

    # Fallback
    logger.warning(f"Date Query: Unrecognized date query: '{command}'")
    _speak_multilang(
        "Sorry, I couldn't understand your date query. Please try rephrasing.",
        hi="माफ़ करें, मैं आपकी तारीख पूछताछ समझ नहीं पाया। कृपया पुनः प्रयास करें।",
        fr="Désolé, je n'ai pas compris votre question sur la date. Veuillez reformuler.",
        es="Lo siento, no entendí su consulta de fecha. Por favor reformule.",
        de="Entschuldigung, ich habe Ihre Datumsanfrage nicht verstanden. Bitte formulieren Sie es neu."
    )
