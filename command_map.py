# ✅ Command Map for Fuzzy Matching (Web + Volume + Brightness + Weather + News + Wikipedia + System + Date/Day + Math/Science + Pokémon)

COMMAND_MAP = {

    # 🌐 Web Commands
    "open_youtube": [
        "open youtube", "youtube खोलो", "youtube खोलिए",
        "ouvre youtube", "abre youtube", "öffne youtube"
    ],
    "open_chatgpt": [
        "open chat g p t", "open chatgpt", "chatgpt खोलो",
        "ouvre chatgpt", "abre chatgpt", "öffne chatgpt"
    ],
    "search_google": [
        "search on google", "google पर खोजें", "google खोजो",
        "recherche sur google", "buscar en google", "google durchsuchen"
    ],
    "play_music": [
        "play music", "गाना चलाओ", "गीत बजाओ",
        "jouer de la musique", "reproducir música", "musik abspielen"
    ],

    # 🔊 Volume Control (Unified into "adjust_volume")
    "adjust_volume": [
        # Increase
        "increase volume", "turn up the volume", "वॉल्यूम बढ़ाओ", "आवाज़ बढ़ाओ",
        "augmenter le volume", "monte le son", "subir el volumen", "aumentar volumen",
        "lautstärke erhöhen", "ton lauter machen",
        # Decrease
        "decrease volume", "turn down the volume", "वॉल्यूम घटाओ", "आवाज़ कम करो",
        "baisser le volume", "réduire le volume", "bajar el volumen", "reducir volumen",
        "lautstärke verringern", "ton leiser machen",
        # Mute
        "mute volume", "mute sound", "वॉल्यूम म्यूट करो", "आवाज़ बंद करो",
        "couper le son", "mettre en sourdine", "silenciar volumen", "silenciar el sonido",
        "lautstärke stummschalten", "ton stumm",
        # Max
        "max volume", "set volume to maximum", "अधिकतम वॉल्यूम", "वॉल्यूम फुल करो",
        "volume maximum", "mettre le volume à fond", "volumen máximo", "subir volumen al máximo",
        "maximale lautstärke", "lautstärke ganz hoch",
        # Set volume to specific level
        "set volume to", "adjust volume to", "वॉल्यूम सेट करो", "वॉल्यूम को सेट करो",
        "régler le volume à", "ajuster le volume à", "establecer volumen a", "ajustar el volumen a",
        "lautstärke einstellen auf", "lautstärke setzen auf"
    ],

    # 💡 Brightness Control (Unified into "adjust_brightness")
    "adjust_brightness": [
        # Increase
        "increase brightness", "brighten screen", "make screen brighter",
        "ब्राइटनेस बढ़ाओ", "स्क्रीन को और चमकदार करो",
        "augmenter la luminosité", "éclaircir l'écran", "aumentar el brillo", "hacer la pantalla más brillante",
        "helligkeit erhöhen", "bildschirm heller machen",
        # Decrease
        "decrease brightness", "dim screen", "make screen darker",
        "ब्राइटनेस घटाओ", "स्क्रीन को कम चमकदार करो",
        "réduire la luminosité", "assombrir l'écran", "reducir el brillo", "oscurecer la pantalla",
        "helligkeit verringern", "bildschirm dunkler machen",
        # Set brightness
        "set brightness to", "adjust brightness to", "ब्राइटनेस सेट करो", "ब्राइटनेस को सेट करो",
        "régler la luminosité à", "ajuster la luminosité à", "establecer el brillo a", "ajustar el brillo a",
        "helligkeit einstellen auf", "helligkeit setzen auf"
    ],

    # 🌦️ Weather Info
    "get_weather": [
        # English
        "weather", "temperature", "what's the weather", "current weather", "how’s the weather",
        "is it raining", "is it hot", "is it cold",
        # Hindi
        "मौसम", "मौसम कैसा है", "क्या बारिश हो रही है", "क्या गर्मी है", "क्या ठंड है",
        # French
        "météo", "temps", "quel temps fait-il", "fait-il chaud", "fait-il froid", "pleut-il",
        # Spanish
        "clima", "tiempo", "qué tiempo hace", "¿está lloviendo?", "¿hace calor?", "¿hace frío?",
        # German
        "wetter", "wie ist das wetter", "ist es heiß", "ist es kalt", "regnet es"
    ],

    # 🗞️ News Info
    "get_news": [
        "news", "headlines", "latest news", "breaking news", "show me the news",
        "खबरें", "ताज़ा समाचार", "न्यूज़",
        "actualités", "nouvelles", "titres",
        "noticias", "titulares",
        "nachrichten", "schlagzeilen", "neuesten"
    ],

    # 📚 Wikipedia Search
    "wiki_search": [
        "what is", "who is", "define", "tell me about",
        "क्या है", "कौन है",
        "qu'est-ce que", "qui est",
        "qué es", "quién es",
        "was ist", "wer ist"
    ],

    # 🛑 Exit Command
    "exit_app": [
        "exit", "shutdown", "stop listening", "quit", "turn off", "power off", "close nova",
        "बंद करो", "बाहर निकलो", "सुनना बंद करो",
        "arrête", "quitte",
        "apagar", "salir",
        "beenden", "verlassen"
    ],

    # 💻 System Control
    "shutdown_system": [
        "shutdown system", "turn off computer", "power off", "switch off",
        "सिस्टम बंद", "कंप्यूटर बंद",
        "arrêter le système", "éteindre l'ordinateur", "éteindre le pc",
        "apagar le système", "apagar la computadora", "apaga la compu",
        "system herunterfahren", "computer ausschalten", "ausschalten"
    ],
    "restart_system": [
        "restart", "reboot", "system restart", "reboot the computer",
        "सिस्टम पुनः आरंभ", "रीस्टार्ट", "फिर से शुरू करो",
        "redémarrer", "redémarrage du système", "relancer le système",
        "reiniciar", "reiniciar el sistema", "reinicia la pc",
        "neu starten", "system neu starten", "neustart"
    ],
    "sleep_system": [
        "sleep", "put to sleep", "go to sleep", "sleep mode",
        "स्लीप मोड", "नींद मोड", "सो जाओ",
        "mettre en veille", "mode veille", "mettre en sommeil",
        "modo de suspensión", "poner en reposo", "modo dormir",
        "schlafmodus", "in den schlafmodus versetzen", "ruhezustand"
    ],
    "lock_system": [
        "lock", "lock screen", "secure screen",
        "स्क्रीन लॉक", "लॉक करें", "लॉक करो",
        "verrouiller l'écran", "verrouiller", "sécuriser l'écran",
        "bloquear pantalla", "bloquear", "bloquea la compu",
        "bildschirm sperren", "sperren", "bildschirm sichern"
    ],
    "logout_system": [
        "log out", "sign out", "log me out", "sign off",
        "लॉग आउट", "साइन आउट", "मुझे लॉग आउट करो",
        "se déconnecter", "déconnexion", "déconnecte-moi",
        "cerrar sesión", "desconectar", "salir de la cuenta",
        "abmelden", "ausloggen", "konto abmelden"
    ],

    # ⏰ Alarm Set
    "set_alarm": [
        "set alarm for", "अलार्म सेट करें", "alarme pour",
        "alarma para", "wecker für"
    ],

    # 🔔 Reminder Set
    "set_reminder": [
        "remind me at", "रिमाइंडर सेट करें", "मुझे याद दिलाना",
        "rappelle-moi à",
        "recuérdame a las", "erinnere mich um"
    ],

    # 📅 Date & Holiday Queries
    "date_queries": [
        # Current date/time/day queries
        "what is the date", "what day is it", "what day is today", "what's the date today", "today's date",
        "what is the time", "current time", "time now", "what month is it", "which month is it", "what is the month",
        # Hindi
        "आज तारीख क्या है", "आज कौन सा दिन है", "तारीख बताओ", "समय क्या है", "वर्तमान समय", "समय अभी क्या है",
        "महीना क्या है", "कौन सा महीना है",
        # French
        "quelle est la date", "quel jour sommes-nous", "quelle est la date aujourd'hui", "quelle heure est-il",
        "quel mois sommes-nous", "quel est le mois",
        # Spanish
        "cuál es la fecha", "qué día es hoy", "cuál es la fecha hoy", "qué hora es",
        "qué mes es", "cuál es el mes",
        # German
        "was ist das datum", "welcher tag ist heute", "was ist das heutige datum", "wie spät ist es",
        "welcher monat ist es", "was ist der monat",

        # Specific holidays and leap year queries
        # English
        "when is christmas", "when is diwali", "when is eid", "next holiday", "when is new year",
        "is this year a leap year", "when is the next leap year", "when was the last leap year",
        "which year is a leap year",
        # Hindi
        "क्रिसमस कब है", "दिवाली कब है", "ईद कब है", "अगला त्यौहार कब है", "नया साल कब है",
        "क्या यह वर्ष लीप वर्ष है", "अगला लीप वर्ष कब है", "पिछला लीप वर्ष कब था",
        # French
        "quand est noël", "quand est diwali", "quand est l'aïd", "prochain jour férié", "quand est le nouvel an",
        "est-ce que c'est une année bissextile", "quand est la prochaine année bissextile", "quelle était la dernière année bissextile",
        # Spanish
        "cuándo es navidad", "cuándo es diwali", "cuándo es eid", "próximo feriado", "cuándo es año nuevo",
        "es este año bisiesto", "cuándo es el próximo año bisiesto", "cuándo fue el último año bisiesto",
        # German
        "wann ist weihnachten", "wann ist diwali", "wann ist eid", "nächster feiertag", "wann ist neujahr",
        "ist dieses jahr ein schaltjahr", "wann ist das nächste schaltjahr", "wann war das letzte schaltjahr"
    ],

    # ➗ Math & Calculator Queries
    "math_query": [
        # English
        "what is", "calculate", "solve", "evaluate", "how much is",
        "math problem", "math question", "simplify", "expand",
        "+", "-", "*", "/", "**", "%", "sqrt", "square root",
        "power", "raised to", "to the power of", "log", "logarithm",
        "mod", "remainder", "modulus", "percentage",
        "differentiate", "derivative", "integrate", "integral",
        "limit of", "approaches", "find x", "solve equation",
        "with respect to", "wrt", "plus", "minus", "times",
        "multiplied by", "divided by",
        "area of", "perimeter of", "circumference of", "radius of",
        "convert degrees to radians", "convert radians to degrees",
        "degrees to radians", "radians to degrees",
        "factorial", "permutation", "combination",
        "mean of", "median of", "standard deviation of",
        "temperature in", "convert temperature", "celsius to fahrenheit", "fahrenheit to celsius",
        "convert minutes", "convert hours", "convert time",
        "scientific notation", "standard form",
        "gcd of", "lcm of", "greatest common divisor", "least common multiple",
        # Hindi
        "क्या है", "गणना करो", "कितना है", "गिनो", "गणित सवाल", "गणित प्रश्न",
        "प्लस", "माइनस", "गुणा", "भाग", "जोड़ो", "घटाओ", "गुणा करो", "भाग करो",
        "घात", "घातांक", "पॉवर", "लॉग", "लघुगणक", "वर्गमूल", "प्रतिशत", "शेषफल",
        "समीकरण हल करो", "x खोजो", "सरलीकरण", "विस्तारित करो", "अवकलन", "समाकलन",
        "सीमा", "सीमा का मान", "सीमा क्या है", "x की सीमा",
        "क्षेत्रफल", "परिमाप", "कोण", "डिग्री से रेडियन", "रेडियन से डिग्री",
        "गुणनफल", "क्रमचय", "संचय", "माध्य", "माध्यिका", "मानक विचलन",
        "तापमान", "तापमान रूपांतरण", "सेल्सियस से फ़ारेनहाइट", "फ़ारेनहाइट से सेल्सियस",
        "घंटों में बदलो", "मिनटों में बदलो", "समय बदलो",
        "वैज्ञानिक संकेतन", "मानक रूप",
        "महत्तम समापवर्तक", "लघुत्तम समापवर्त्य", "gcd", "lcm",
        # French
        "quel est", "calcule", "résous", "combien font", "question mathématique",
        "plus", "moins", "fois", "divisé par", "élevé à", "puissance",
        "racine carrée", "logarithme", "pourcentage", "modulo",
        "intégrer", "dériver", "limite de", "approche", "trouver x",
        "simplifier", "développer",
        "aire de", "périmètre de", "conversion degrés en radians", "radians en degrés",
        "factorielle", "permutation", "combinaison",
        "moyenne de", "médiane de", "écart type de",
        "convertir la température", "celsius en fahrenheit", "fahrenheit en celsius",
        "convertir minutes", "convertir heures", "convertir temps",
        "notation scientifique", "forme standard",
        "pgcd", "ppcm", "plus grand diviseur commun", "plus petit multiple commun",
        # Spanish
        "cuánto es", "calcula", "resuelve", "problema matemático",
        "más", "menos", "por", "dividido por", "elevado a", "potencia",
        "raíz cuadrada", "logaritmo", "porcentaje", "residuo",
        "diferenciar", "integrar", "resolver", "simplificar", "expandir",
        "hallar x", "límite de", "tiende a",
        "área de", "perímetro de", "convertir grados a radianes", "radianes a grados",
        "factorial", "permutación", "combinación",
        "media de", "mediana de", "desviación estándar de",
        "convertir temperatura", "celsius a fahrenheit", "fahrenheit a celsius",
        "convertir minutos", "convertir horas", "convertir tiempo",
        "notación científica", "forma estándar",
        "mcd", "mcm", "máximo común divisor", "mínimo común múltiplo",
        # German
        "was ist", "berechne", "rechne", "wie viel ist", "matheaufgabe",
        "plus", "minus", "mal", "geteilt durch", "hoch", "potenz",
        "quadratwurzel", "logarithmus", "prozent", "rest",
        "differenzieren", "integrieren", "gleichung lösen", "x finden",
        "vereinfachen", "erweitern", "grenze von", "gegen", "x nähert sich",
        "fläche von", "umfang von", "grad in bogenmaß", "bogenmaß in grad",
        "fakultät", "permutation", "kombination",
        "mittelwert von", "median von", "standardabweichung von",
        "temperatur umrechnen", "celsius zu fahrenheit", "fahrenheit zu celsius",
        "zeit umrechnen", "minuten zu stunden", "stunden zu minuten",
        "wissenschaftliche notation", "standardform",
        "ggt", "kgv", "größter gemeinsamer teiler", "kleinstes gemeinsames vielfaches"
    ],

    # 📊 Plotting Commands
    "plot_command": [
        # English
        "plot", "graph", "draw graph", "sketch graph", "graph equation", "graph this",
        "plot this", "graph of", "plot y equals", "draw function", "visualize function",
        "show me the graph", "graphically show", "graph function", "plot the function",
        "plot y vs x", "plot x versus y",
        # Hindi
        "ग्राफ बनाओ", "ग्राफ दिखाओ", "रेखा चित्र", "ग्राफ खींचो", "चित्र बनाओ", "चित्र दिखाओ",
        # French
        "trace le graphique", "dessiner le graphique", "graphe de", "visualiser la fonction",
        # Spanish
        "traza el gráfico", "dibujar el gráfico", "gráfico de", "visualizar la función",
        # German
        "zeichne das diagramm", "zeichne den graph", "graph darstellen", "funktion darstellen"
    ],

    # ⚛️ Physics
    "physics_query": [
        # English
        "physics mode", "solve physics", "physics problem", "use physics",
        "kinematics", "projectile", "time of flight", "range", "maximum height",
        "newton's laws", "newtons law", "f = m a", "f=ma",
        "work energy", "kinetic energy", "potential energy", "power",
        "circular motion", "angular velocity", "torque", "moment of inertia",
        "ohm's law", "ohms law", "v = i r", "v=i*r", "p = v i", "p=vi",
        "capacitance", "inductance", "impedance",
        "snell's law", "refraction", "wavelength", "frequency",
        "simple harmonic motion", "shm", "spring constant",
        "escape velocity", "gravitational field",
        "magnetic field strength", "magnetic field", "magnetic flux", "flux",
        "magnetic flux density", "emf", "electromotive force",
        "resistance",
        "inductive reactance", "capacitive reactance", "impedance",
        "viscosity", "buoyant force", "density",
        "refractive index", "fringe width",
        "angular momentum", "normal force", "coefficient of friction",
        # Hindi
        "भौतिकी", "फिजिक्स मोड", "भौतिकी प्रश्न", "गतिकी", "प्रक्षेप्य", "उड़ान का समय",
        "परास", "अधिकतम ऊंचाई", "न्यूटन का नियम", "कार्य ऊर्जा", "गतिज ऊर्जा", "स्थितिज ऊर्जा",
        "वृत्तीय गति", "घूर्णन वेग", "टॉर्क", "जड़त्व आघूर्ण", "ओम का नियम",
        "चुंबकीय क्षेत्र", "चुंबकीय क्षेत्र की तीव्रता", "चुंबकीय फ्लक्स", "चुंबकीय प्रवाह",
        "चुंबकीय फ्लक्स घनत्व", "ई एम एफ", "वैद्युतचालक बल",
        "प्रतिरोध",
        "प्रेरक रिएक्टेंस", "धारिता रिएक्टेंस", "इम्पीडेंस",
        "सांद्रता", "उत्थापन बल", "घनत्व",
        "अपवर्तांक", "फ्रिंज चौड़ाई", "पट्टी चौड़ाई",
        "कोणीय संवेग", "सामान्य बल", "लंब बल", "घर्षण गुणांक",
        # French
        "mode physique", "problème de physique", "cinématique", "projectile",
        "temps de vol", "portée", "lois de newton", "énergie cinétique",
        "énergie potentielle", "puissance", "mouvement circulaire", "vitesse angulaire",
        "couple", "moment d'inertie", "loi d'ohm", "réfraction", "longueur d'onde",
        "fréquence", "mouvement harmonique simple",
        "intensité du champ magnétique", "champ magnétique", "flux magnétique",
        "densité de flux magnétique", "f.e.m.", "force électromotrice",
        "résistance", "réactance inductive", "réactance capacitive", "impédance",
        "viscosité", "poussée d'archimède", "force de flottabilité", "densité",
        "indice de réfraction", "largeur de frange",
        "moment cinétique", "force normale", "coefficient de frottement",
        # Spanish
        "modo física", "problema de física", "cinemática", "proyectil",
        "tiempo de vuelo", "alcance", "leyes de newton", "energía cinética",
        "energía potencial", "potencia", "movimiento circular", "velocidad angular",
        "par de torsión", "momento de inercia", "ley de ohm", "refracción",
        "longitud de onda", "frecuencia", "mrua", "mhs",
        "intensidad del campo magnético", "campo magnético", "flujo magnético",
        "densidad de flujo magnético", "f.e.m.", "fuerza electromotriz",
        "resistencia", "reactancia inductiva", "reactancia capacitiva", "impedancia",
        "viscosidad", "fuerza de flotación", "empuje", "densidad",
        "índice de refracción", "anchura de franjas", "ancho de franjas",
        "momento angular", "fuerza normal", "coeficiente de fricción",
        # German
        "physik modus", "physikaufgabe", "kinematik", "projektil",
        "flugzeit", "reichweite", "newtons gesetz", "kinetische energie",
        "potentielle energie", "leistung", "kreisbewegung", "winkelgeschwindigkeit",
        "drehmoment", "trägheitsmoment", "ohmsches gesetz", "brechung",
        "wellenlänge", "frequenz", "harmonische schwingung",
        "magnetfeldstärke", "magnetfeld", "magnetischer fluss",
        "magnetische flussdichte", "emk", "elektromotorische kraft",
        "widerstand", "induktive reaktanz", "kapazitive reaktanz", "impedanz",
        "viskosität", "auftriebskraft", "auftrieb", "dichte",
        "brechungsindex", "streifenbreite",
        "drehimpuls", "normalkraft", "reibungskoeffizient"
    ],

    # ✅ Graph / Plot confirmation
    "physics_graph_confirm": [
        # English
        "graph it", "plot it", "show graph", "show the graph", "yes", "yeah", "yup", "ok", "okay", "sure",
        # Hindi
        "ग्राफ दिखाओ", "ग्राफ बनाओ", "हाँ", "ठीक है",
        # French
        "trace le graphique", "affiche le graphe", "oui", "d'accord",
        # Spanish
        "traza el gráfico", "muestra el gráfico", "sí", "vale", "ok",
        # German
        "zeichne den graph", "diagramm anzeigen", "ja", "ok", "okay", "klar"
    ],

    # 🧪 Chemistry (calculations, equations, solution prep)
    "chemistry_query": [
        # English
        "chemistry mode", "solve chemistry", "chemistry problem", "use chemistry",
        "molar mass of", "molecular weight of", "formula mass of",
        "stoichiometry", "stoichiometric", "limiting reagent", "limiting reactant",
        "empirical formula", "molecular formula",
        "percent composition", "percentage composition",
        "molarity", "molality", "normality", "dilution", "prepare solution",
        "concentration", "ppm", "ppb", "millimolar", "micromolar", "mm", "μm", "um",
        "ph of", "poh of", "acid base", "strong acid", "strong base",
        "henderson hasselbalch", "buffer ph", "buffer capacity",
        "ideal gas law", "pv=nrt", "boyle", "charles", "gay lussac", "combined gas law", "avogadro law",
        "gas law", "r value", "partial pressure", "density of gas",
        # Hindi
        "रसायन विज्ञान", "केमिस्ट्री मोड", "केमिस्ट्री सवाल", "रसायन प्रश्न",
        "मोलर द्रव्यमान", "आणविक भार", "सूत्र द्रव्यमान",
        "स्टॉयकीयोमेट्री", "सीमित अभिकारक", "एम्पिरिकल फॉर्मूला", "मॉलैरिटी", "डाइल्यूशन", "घोल तैयार करना",
        "पीएच", "पीओएच", "एसिड बेस", "आदर्श गैस नियम", "बॉयल का नियम", "चार्ल्स का नियम",
        # French
        "mode chimie", "problème de chimie", "résoudre en chimie",
        "masse molaire de", "masse moléculaire de", "masse formule de",
        "stœchiométrie", "réactif limitant", "formule empirique", "formule moléculaire",
        "composition massique", "molarité", "molalité", "dilution", "préparer une solution",
        "ph de", "poh de", "acide fort", "base forte",
        "loi des gaz idéale", "boyle", "charles", "gay lussac", "pv=nrt",
        # Spanish
        "modo química", "problema de química", "resolver química",
        "masa molar de", "peso molecular de", "masa fórmula de",
        "estequiometría", "reactivo limitante", "fórmula empírica", "fórmula molecular",
        "porcentaje en masa", "molaridad", "molalidad", "dilución", "preparar solución",
        "ph de", "poh de", "ácido fuerte", "base fuerte",
        "ley de gases ideal", "boyle", "charles", "gay lussac", "pv=nrt",
        # German
        "chemie modus", "chemieaufgabe", "chemie lösen",
        "molare masse von", "molekulargewicht von", "formelmasse von",
        "stöchiometrie", "limitierender reaktant", "empirische formel", "molekülformel",
        "molarität", "molalität", "verdünnung", "lösung herstellen",
        "ph von", "poh von", "starke säure", "starke base",
        "ideale gasgleichung", "boyle", "charles", "gay-lussac", "pv=nrt"
    ],

    # 📇 Chemistry Quick Facts
    "chemistry_fact": [
        # English
        "element", "atomic number of", "atomic mass of", "symbol of", "name of element",
        "group of", "period of", "block of", "category of", "series of",
        "electron configuration of", "valency of", "oxidation states of",
        "electronegativity of", "atomic radius of", "ionic radius of",
        "density of", "melting point of", "boiling point of", "phase of",
        # Hindi
        "तत्व", "परमाणु संख्या", "परमाणु द्रव्यमान", "प्रत_symbol", "समूह", "आवर्त",
        "इलेक्ट्रॉन विन्यास", "संयोजकता", "ऑक्सीकरण अवस्थाएँ",
        "विद्युतऋणात्मकता", "घनत्व", "गलनांक", "उबलांक",
        # French
        "numéro atomique de", "masse atomique de", "symbole de", "groupe de", "période de",
        "configuration électronique de", "valence de", "états d'oxydation de",
        "électronégativité de", "densité de", "point de fusion de", "point d'ébullition de",
        # Spanish
        "número atómico de", "masa atómica de", "símbolo de", "grupo de", "período de",
        "configuración electrónica de", "valencia de", "estados de oxidación de",
        "electronegatividad de", "densidad de", "punto de fusión de", "punto de ebullición de",
        # German
        "ordnungszahl von", "atommasse von", "symbol von", "gruppe von", "periode von",
        "elektronenkonfiguration von", "wertigkeit von", "oxidationsstufen von",
        "elektronegativität von", "dichte von", "schmelzpunkt von", "siedepunkt von"
    ],

    # 🐾 Pokémon (Nova ↔ FastAPI)

    # List all Pokémon
    "pokemon_list": [
        # EN
        "list pokemon", "show pokemon", "show pokémon", "my pokemon", "open pokedex", "open pokédex", "pokedex", "pokédex",
        # HI
        "पोकेमोन दिखाओ", "मेरे पोकेमोन", "पोकेमोन सूची", "पोकेडेक्स", "पोकिडेक्स",
        # FR
        "liste pokémon", "affiche pokémon", "affiche mes pokémon", "ouvrir pokédex", "pokédex",
        # ES
        "lista pokémon", "muestra pokémon", "muestra mis pokémon", "abrir pokédex", "pokédex",
        # DE
        "pokemon auflisten", "zeige pokémon", "meine pokémon anzeigen", "pokédex öffnen", "pokédex"
    ],

    # List filtered by TYPE
    "pokemon_list_type": [
        # English
        "list bug type", "show bug type",
        "list dark type", "show dark type",
        "list dragon type", "show dragon type",
        "list electric type", "show electric type",
        "list fairy type", "show fairy type",
        "list fighting type", "show fighting type",
        "list fire type", "show fire type",
        "list flying type", "show flying type",
        "list ghost type", "show ghost type",
        "list grass type", "show grass type",
        "list ground type", "show ground type",
        "list ice type", "show ice type",
        "list normal type", "show normal type",
        "list poison type", "show poison type",
        "list psychic type", "show psychic type",
        "list rock type", "show rock type",
        "list steel type", "show steel type",
        "list water type", "show water type",
        # Hindi
        "बग टाइप दिखाओ", "डार्क टाइप दिखाओ",
        "ड्रैगन टाइप दिखाओ", "इलेक्ट्रिक टाइप दिखाओ",
        "फेयरी टाइप दिखाओ", "फाइटिंग टाइप दिखाओ",
        "फायर टाइप दिखाओ", "फ्लाइंग टाइप दिखाओ",
        "घोस्ट टाइप दिखाओ", "ग्रास टाइप दिखाओ",
        "ग्राउंड टाइप दिखाओ", "आइस टाइप दिखाओ",
        "नॉर्मल टाइप दिखाओ", "पॉइज़न टाइप दिखाओ",
        "साइकीक टाइप दिखाओ", "रॉक टाइप दिखाओ",
        "स्टील टाइप दिखाओ", "वॉटर टाइप दिखाओ",
        # French
        "liste type insecte", "affiche type insecte",
        "liste type ténèbres", "affiche type ténèbres",
        "liste type dragon", "affiche type dragon",
        "liste type électrik", "affiche type électrik",
        "liste type fée", "affiche type fée",
        "liste type combat", "affiche type combat",
        "liste type feu", "affiche type feu",
        "liste type vol", "affiche type vol",
        "liste type spectre", "affiche type spectre",
        "liste type plante", "affiche type plante",
        "liste type sol", "affiche type sol",
        "liste type glace", "affiche type glace",
        "liste type normal", "affiche type normal",
        "liste type poison", "affiche type poison",
        "liste type psy", "affiche type psy",
        "liste type roche", "affiche type roche",
        "liste type acier", "affiche type acier",
        "liste type eau", "affiche type eau",
        # Spanish
        "lista tipo bicho", "muestra tipo bicho",
        "lista tipo siniestro", "muestra tipo siniestro",
        "lista tipo dragón", "muestra tipo dragón",
        "lista tipo eléctrico", "muestra tipo eléctrico",
        "lista tipo hada", "muestra tipo hada",
        "lista tipo lucha", "muestra tipo lucha",
        "lista tipo fuego", "muestra tipo fuego",
        "lista tipo volador", "muestra tipo volador",
        "lista tipo fantasma", "muestra tipo fantasma",
        "lista tipo planta", "muestra tipo planta",
        "lista tipo tierra", "muestra tipo tierra",
        "lista tipo hielo", "muestra tipo hielo",
        "lista tipo normal", "muestra tipo normal",
        "lista tipo veneno", "muestra tipo veneno",
        "lista tipo psíquico", "muestra tipo psíquico",
        "lista tipo roca", "muestra tipo roca",
        "lista tipo acero", "muestra tipo acero",
        "lista tipo agua", "muestra tipo agua",
        # German
        "liste käfer typ", "zeige käfer typ",
        "liste unlicht typ", "zeige unlicht typ",
        "liste drache typ", "zeige drache typ",
        "liste elektro typ", "zeige elektro typ",
        "liste fee typ", "zeige fee typ",
        "liste kampf typ", "zeige kampf typ",
        "liste feuer typ", "zeige feuer typ",
        "liste flug typ", "zeige flug typ",
        "liste geist typ", "zeige geist typ",
        "liste pflanze typ", "zeige pflanze typ",
        "liste boden typ", "zeige boden typ",
        "liste eis typ", "zeige eis typ",
        "liste normal typ", "zeige normal typ",
        "liste gift typ", "zeige gift typ",
        "liste psycho typ", "zeige psycho typ",
        "liste gestein typ", "zeige gestein typ",
        "liste stahl typ", "zeige stahl typ",
        "liste wasser typ", "zeige wasser typ"
    ],

    # Show one
    "pokemon_show": [
        # EN
        "show pokemon", "show pokémon", "pokemon details", "pokémon details",
        # HI
        "पोकेमोन दिखाओ", "पोकेमोन विवरण",
        # FR
        "affiche pokémon", "détails pokémon",
        # ES
        "muestra pokémon", "detalles de pokémon",
        # DE
        "zeige pokémon", "pokémon details"
    ],

    # Add
    "pokemon_add": [
        # EN
        "add pokemon", "add pokémon", "add new pokemon", "create pokemon",
        # HI
        "पोकेमोन जोड़ो", "नया पोकेमोन जोड़ो",
        # FR
        "ajouter pokémon", "créer pokémon",
        # ES
        "agregar pokémon", "añadir pokémon", "crear pokémon",
        # DE
        "pokemon hinzufügen", "pokémon hinzufügen", "pokemon erstellen"
    ],

    # Update
    "pokemon_update": [
        # EN
        "update pokemon", "edit pokemon", "set level", "change level", "set type", "change type", "set nickname", "rename pokemon",
        # HI
        "पोकेमोन अपडेट", "पोकेमोन बदलो", "लेवल सेट", "टाइप बदलो", "निकनेम बदलो",
        # FR
        "mettre à jour pokémon", "modifier pokémon", "définir niveau", "changer type", "renommer pokémon",
        # ES
        "actualizar pokémon", "editar pokémon", "poner nivel", "cambiar tipo", "cambiar apodo", "renombrar pokémon",
        # DE
        "pokemon aktualisieren", "pokemon bearbeiten", "level setzen", "typ ändern", "spitznamen ändern", "pokemon umbenennen"
    ],

    # Delete
    "pokemon_delete": [
        # EN
        "delete pokemon", "remove pokemon", "delete pokémon", "remove pokémon",
        # HI
        "पोकेमोन हटाओ", "पोकेमोन डिलीट",
        # FR
        "supprimer pokémon", "retirer pokémon",
        # ES
        "eliminar pokémon", "borrar pokémon",
        # DE
        "pokemon löschen", "pokémon entfernen"
    ],

    # Help
    "pokemon_help": [
        # EN
        "pokemon help", "help pokemon", "how to use pokemon",
        # HI
        "पोकेमोन मदद", "पोकेमोन हेल्प",
        # FR
        "aide pokémon", "aide pour pokémon",
        # ES
        "ayuda pokémon", "cómo usar pokémon",
        # DE
        "hilfe pokémon", "wie benutzt man pokémon"
    ],

    # 🐾 Pokémon – Images / Gallery (merged)
    "pokemon_image": [
        # English (scoped to Pokémon)
        "upload pokemon image", "add pokemon image", "attach pokemon image",
        "upload image for pokemon", "upload image for pokémon",
        "show pokemon image", "set image for pokemon", "add image to pokemon",
        # Hindi (scoped)
        "पोकेमोन इमेज अपलोड करो", "पोकेमोन की तस्वीर जोड़ो", "पोकेमोन इमेज सेट करो", "पोकेमोन तस्वीर दिखाओ",
        # French (scoped)
        "téléverser image pokémon", "ajouter image pokémon", "afficher l'image du pokémon", "définir l'image du pokémon",
        # Spanish (scoped)
        "subir imagen pokémon", "añadir imagen pokémon", "mostrar imagen del pokémon", "poner imagen al pokémon", "añadir imagen al pokémon",
        # German (scoped)
        "pokémon-bild hochladen", "pokémon-bild hinzufügen", "pokémon bild anzeigen", "bild für pokémon setzen", "bild zum pokémon hinzufügen"
    ],

    # (Optional) separate multi-image trigger group if you want to distinguish
    "pokemon_image_multi": [
        # English (scoped)
        "upload pokemon images", "add pokemon images", "attach pokemon images",
        # Hindi (scoped)
        "कई पोकेमोन इमेज अपलोड", "कई पोकेमोन तस्वीरें जोड़ो",
        # French (scoped)
        "téléverser des images pokémon",
        # Spanish (scoped)
        "subir imágenes de pokémon", "añadir imágenes de pokémon",
        # German (scoped)
        "mehrere pokémon-bilder hochladen", "pokémon-bilder hinzufügen"
    ],

    # Explicit gallery open triggers (scoped to Pokémon)
    "pokemon_gallery_open": [
        "open pokemon gallery", "show pokemon gallery",
        "पोकेमोन गैलरी खोलो",
        "ouvrir la galerie pokémon",
        "abrir galería de pokémon",
        "pokémon-galerie öffnen"
    ],

    # 🐾 Pokémon – Download image (scoped to Pokémon)
    "pokemon_download": [
        # English
        "download pokemon image", "save pokemon image",
        # Hindi
        "पोकेमोन इमेज डाउनलोड",
        # French
        "télécharger l'image pokémon", "enregistrer l'image pokémon",
        # Spanish
        "descargar imagen pokémon", "guardar imagen pokémon",
        # German
        "pokémon-bild herunterladen", "pokémon-bild speichern"
    ],

    # 🐾 Pokémon – Import CSV (scoped to Pokémon)
    "pokemon_import_csv": [
        # English
        "import pokemon csv",
        # Hindi
        "पोकेमोन सीएसवी इम्पोर्ट",
        # French
        "importer csv pokémon",
        # Spanish
        "importar csv de pokémon",
        # German
        "pokémon-csv importieren"
    ],

    # 🐾 Pokémon – Team (names aligned with handlers)
    "team_list": [
        "list team", "show team",
        "टीम दिखाओ", "équipe afficher", "mostrar equipo", "team anzeigen"
    ],
    "team_add": [
        "add to team", "add pokemon to team",
        "टीम में जोड़ो", "ajouter à l'équipe",
        "añadir al equipo", "agregar al equipo",
        "zum team hinzufügen"
    ],
    "team_remove": [
        "remove from team", "delete from team",
        "टीम से हटाओ", "retirer de l'équipe",
        "quitar del equipo", "eliminar del equipo",
        "aus dem team entfernen"
    ],
    "team_upgrade": [
        "upgrade team", "set team level", "team level set", "team member level",
        "टीम अपग्रेड", "टीम लेवल सेट",
        "améliorer l’équipe", "niveau de l’équipe",
        "mejorar equipo", "nivel del equipo",
        "team upgrade", "team level setzen"
    ],
    "team_average": [
        "team average level", "average team level",
        "team ka ausat level",
        "niveau moyen de l'équipe",
        "nivel medio del equipo", "nivel promedio del equipo",
        "durchschnittliches teamniveau", "durchschnittliches team level"
    ],

    # 🐾 Trainer profile (names aligned with handlers)
    "trainer_me": [
        "trainer profile", "show my trainer profile", "my trainer profile",
        "ट्रेनर प्रोफ़ाइल दिखाओ", "mon profil dresseur",
        "mi perfil de entrenador", "mein trainerprofil"
    ],
    "trainer_update": [
        "trainer nickname is", "trainer name is", "nickname is", "name is",
        "location is", "city is", "place is",
        "pronouns are", "pronoun is",
        # Hindi
        "ट्रेनर निकनेम है", "निकनेम है", "ट्रेनर नाम है", "नाम है",
        "स्थान है", "शहर है", "जगह है",
        "प्रोनाउन हैं", "प्रोनाउन है",
        # French
        "le surnom du dresseur est", "mon surnom est", "la localisation est", "les pronoms sont",
        # Spanish
        "el apodo del entrenador es", "mi apodo es", "la ubicación es", "los pronombres son",
        # German
        "trainer spitzname ist", "mein spitzname ist", "ort ist", "pronomen sind"
    ]

}