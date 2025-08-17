# handlers/holiday_commands.py

import datetime
import difflib
import re

def handle_holiday_queries(command: str) -> None:
    command = command.lower()

    # Lazy import of utils only
    from utils import _speak_multilang, logger

    # Static fallback dates for holidays not covered by holidays package
    static_holidays = {
        "christmas": "December 25",
        "new year": "January 1",
        "diwali": "November 4",  # Approximate, lunar calendar varies yearly
        "eid": "April 21"        # Approximate
    }

    # Holiday keywords across languages
    holiday_keywords = [
        "christmas", "diwali", "eid", "new year",
        "क्रिसमस", "दिवाली", "ईद", "नया साल",
        "noël", "aïd", "nouvel an",
        "navidad", "año nuevo",
        "weihnachten", "neujahr"
    ]

    # Use fuzzy matching to detect holiday from user command
    possible_matches = difflib.get_close_matches(command, holiday_keywords, n=1, cutoff=0.6)
    holiday_mentioned = possible_matches[0] if possible_matches else None

    if not holiday_mentioned:
        logger.warning(f"Holiday Query: No matching holiday found in command '{command}'")
        _speak_multilang(
            "Sorry, I couldn't find the holiday you mentioned.",
            hi="माफ़ करें, मैं उस छुट्टी को नहीं पहचान पाया।",
            fr="Désolé, je n'ai pas trouvé le jour férié que vous avez mentionné.",
            es="Lo siento, no pude encontrar el feriado que mencionaste.",
            de="Entschuldigung, ich konnte den genannten Feiertag nicht finden."
        )
        return

    now = datetime.datetime.now()
    year = now.year

    # Year context adjustment
    if any(kw in command for kw in ["last year", "पिछला साल", "l'année dernière", "el año pasado", "letztes jahr"]):
        year -= 1
    elif any(kw in command for kw in ["next year", "अगला साल", "l'année prochaine", "el próximo año", "nächstes jahr"]):
        year += 1

    # Try to import holidays package locally
    try:
        import holidays
        country_holidays = holidays.CountryHoliday('IN', years=year)
    except ImportError:
        country_holidays = None
        logger.error("Holiday Query: holidays package not installed")

    # Map multilingual names to English keys for lookup
    holiday_map = {
        "christmas": "Christmas Day",
        "क्रिसमस": "Christmas Day",
        "noël": "Christmas Day",
        "navidad": "Christmas Day",
        "weihnachten": "Christmas Day",

        "new year": "New Year's Day",
        "नया साल": "New Year's Day",
        "nouvel an": "New Year's Day",
        "año nuevo": "New Year's Day",
        "neujahr": "New Year's Day",

        "diwali": "Diwali",
        "दिवाली": "Diwali",

        "eid": "Eid",
        "ईद": "Eid"
    }

    eng_name = holiday_map.get(holiday_mentioned, holiday_mentioned)

    date_of_holiday = None
    if country_holidays:
        for date, name in country_holidays.items():
            if name.lower() == eng_name.lower():
                date_of_holiday = date
                break

    # If not found in holidays package, fallback to static with lunar disclaimer
    if not date_of_holiday:
        static_date = static_holidays.get(holiday_mentioned)
        if static_date:
            response = (f"{eng_name} is usually on {static_date}. Exact date varies each year.")
            logger.info(f"Holiday Query (Fallback): Command='{command}', Response='{response}'")
            _speak_multilang(
                response,
                hi=f"{eng_name} आमतौर पर {static_date} को होता है। सही तारीख हर साल बदलती है।",
                fr=f"{eng_name} a lieu généralement le {static_date}. La date exacte varie chaque année.",
                es=f"{eng_name} suele ser el {static_date}. La fecha exacta varía cada año.",
                de=f"{eng_name} findet normalerweise am {static_date} statt. Das genaue Datum variiert jedes Jahr."
            )
            return
        else:
            logger.warning(f"Holiday Query: No info available for '{holiday_mentioned}'")
            _speak_multilang(
                "Sorry, I don't have information about that holiday.",
                hi="माफ़ करें, मेरे पास उस छुट्टी की जानकारी नहीं है।",
                fr="Désolé, je n'ai pas d'informations sur ce jour férié.",
                es="Lo siento, no tengo información sobre ese feriado.",
                de="Entschuldigung, ich habe keine Informationen zu diesem Feiertag."
            )
            return

    # Adjust year if different
    if date_of_holiday.year != year:
        try:
            date_of_holiday = date_of_holiday.replace(year=year)
        except ValueError:
            logger.warning(f"Holiday Query: Invalid date replacement for {eng_name} in year {year}")
            pass

    date_str = date_of_holiday.strftime("%B %d, %Y")
    response = f"{eng_name} is on {date_str}."
    logger.info(f"Holiday Query: Command='{command}', Response='{response}'")

    _speak_multilang(
        response,
        hi=f"{eng_name} {date_str} को है।",
        fr=f"{eng_name} est le {date_str}.",
        es=f"{eng_name} es el {date_str}.",
        de=f"{eng_name} ist am {date_str}."
    )
