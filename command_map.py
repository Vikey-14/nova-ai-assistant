# ✅ Command Map for Fuzzy Matching (Web + Volume + Brightness + Weather + News + Wikipedia + System + Date/Day)

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
        # Set brightness to specific level
        "set brightness to", "adjust brightness to", "ब्राइटनेस सेट करो", "ब्राइटनेस को सेट करो",
        "régler la luminosité à", "ajuster la luminosité à", "establecer el brillo a", "ajustar el brillo a",
        "helligkeit einstellen auf", "helligkeit setzen auf"
    ],

    # 🌦️ Weather Info
    "get_weather": [
        # 🔵 English
        "weather", "temperature", "what's the weather", "current weather", "how’s the weather",
        "is it raining", "is it hot", "is it cold",

        # 🔴 Hindi
        "मौसम", "मौसम कैसा है", "क्या बारिश हो रही है", "क्या गर्मी है", "क्या ठंड है",

        # 🟢 French
        "météo", "temps", "quel temps fait-il", "fait-il chaud", "fait-il froid", "pleut-il",

        # 🟡 Spanish
        "clima", "tiempo", "qué tiempo hace", "¿está lloviendo?", "¿hace calor?", "¿hace frío?",

        # 🔵 German
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

        # Specific holidays and leap year queries including last leap year
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

    # ➗ Math & Calculator Queries (Basic + Advanced + Symbolic + Matrix)
    "math_query": [
        # 🔵 English
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

        # 🔴 Hindi (हिंदी)
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

        # 🟢 French (Français)
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

        # 🟡 Spanish (Español)
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

        # 🔵 German (Deutsch)
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

    # 📊 Plotting Commands (Symbolic + Custom Points)
    "plot_command": [
        # 🔵 English
        "plot", "graph", "draw graph", "sketch graph", "graph equation", "graph this",
        "plot this", "graph of", "plot y equals", "draw function", "visualize function",
        "show me the graph", "graphically show", "graph function", "plot the function",
        "plot y vs x", "plot x versus y",

        # 🔴 Hindi
        "ग्राफ बनाओ", "ग्राफ दिखाओ", "रेखा चित्र", "ग्राफ खींचो", "चित्र बनाओ", "चित्र दिखाओ",

        # 🟢 French
        "trace le graphique", "dessiner le graphique", "graphe de", "visualiser la fonction",

        # 🟡 Spanish
        "traza el gráfico", "dibujar el gráfico", "gráfico de", "visualizar la fonction",

        # 🔵 German
        "zeichne das diagramm", "zeichne den graph", "graph darstellen", "funktion darstellen"
    ],

    # ⚛️ Physics (problem-solving, formulas, units)
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

    # ✅ Graph / Plot 
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

    # 🧪 Chemistry (calculations, equations, and solution prep)
    "chemistry_query": [
        # 🔵 English — calculations & problem phrases
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

        # 🔴 Hindi — गणना/समाधान
        "रसायन विज्ञान", "केमिस्ट्री मोड", "केमिस्ट्री सवाल", "रसायन प्रश्न",
        "मोलर द्रव्यमान", "आणविक भार", "सूत्र द्रव्यमान",
        "स्टॉयकीयोमेट्री", "सीमित अभिकारक", "एम्पिरिकल फॉर्मूला", "मॉलैरिटी", "डाइल्यूशन", "घोल तैयार करना",
        "पीएच", "पीओएच", "एसिड बेस", "आदर्श गैस नियम", "बॉयल का नियम", "चार्ल्स का नियम",

        # 🟢 French — calculs
        "mode chimie", "problème de chimie", "résoudre en chimie",
        "masse molaire de", "masse moléculaire de", "masse formule de",
        "stœchiométrie", "réactif limitant", "formule empirique", "formule moléculaire",
        "composition massique", "molarité", "molalité", "dilution", "préparer une solution",
        "ph de", "poh de", "acide fort", "base forte",
        "loi des gaz idéale", "boyle", "charles", "gay lussac", "pv=nrt",

        # 🟡 Spanish — cálculos
        "modo química", "problema de química", "resolver química",
        "masa molar de", "peso molecular de", "masa fórmula de",
        "estequiometría", "reactivo limitante", "fórmula empírica", "fórmula molecular",
        "porcentaje en masa", "molaridad", "molalidad", "dilución", "preparar solución",
        "ph de", "poh de", "ácido fuerte", "base fuerte",
        "ley de gases ideal", "boyle", "charles", "gay lussac", "pv=nrt",

        # 🔵 German — Rechnungen
        "chemie modus", "chemieaufgabe", "chemie lösen",
        "molare masse von", "molekulargewicht von", "formelmasse von",
        "stöchiometrie", "limitierender reaktant", "empirische formel", "molekülformel",
        "molarität", "molalität", "verdünnung", "lösung herstellen",
        "ph von", "poh von", "starke säure", "starke base",
        "ideale gasgleichung", "boyle", "charles", "gay-lussac", "pv=nrt"
    ],

    # 📇 Chemistry Quick Facts (periodic-table lookups / properties)
    "chemistry_fact": [
        # 🔵 English — element/property lookups
        "element", "atomic number of", "atomic mass of", "symbol of", "name of element",
        "group of", "period of", "block of", "category of", "series of",
        "electron configuration of", "valency of", "oxidation states of",
        "electronegativity of", "atomic radius of", "ionic radius of",
        "density of", "melting point of", "boiling point of", "phase of",

        # 🔴 Hindi — त्वरित तथ्य
        "तत्व", "परमाणु संख्या", "परमाणु द्रव्यमान", "प्रत_symbol", "समूह", "आवर्त",
        "इलेक्ट्रॉन विन्यास", "संयोजकता", "ऑक्सीकरण अवस्थाएँ",
        "विद्युतऋणात्मकता", "घनत्व", "गलनांक", "उबलांक",

        # 🟢 French — fiches élémentaires
        "numéro atomique de", "masse atomique de", "symbole de", "groupe de", "période de",
        "configuration électronique de", "valence de", "états d'oxydation de",
        "électronégativité de", "densité de", "point de fusion de", "point d'ébullition de",

        # 🟡 Spanish — datos rápidos
        "número atómico de", "masa atómica de", "símbolo de", "grupo de", "período de",
        "configuración electrónica de", "valencia de", "estados de oxidación de",
        "electronegatividad de", "densidad de", "punto de fusión de", "punto de ebullición de",

        # 🔵 German — Elementdaten
        "ordnungszahl von", "atommasse von", "symbol von", "gruppe von", "periode von",
        "elektronenkonfiguration von", "wertigkeit von", "oxidationsstufen von",
        "elektronegativität von", "dichte von", "schmelzpunkt von", "siedepunkt von"
    ]
}
