# 📘 normalizer.py — Hinglish → Hindi (Devanagari) Normalizer

import re


# Base Hinglish → Hindi map (general + math/UX), digits kept ASCII
hinglish_map = {
    # 🌦️ Weather & Time
    "mausam": "मौसम",
    "taapmaan": "तापमान",
    "taapman": "तापमान",
    "aaj": "आज",
    "kal": "कल",
    "din": "दिन",
    "day": "दिन",
    "samay": "समय",
    "ghanta": "घंटा",
    "minute": "मिनट",
    "baje": "बजे",
    "abhi": "अभी",
    "subah": "सुबह",
    "shaam": "शाम",
    "raat": "रात",
    "month": "महीना",
    "mahina": "महीना",
    "saal": "साल",
    "varsh": "वर्ष",
    "salana": "सालाना",
    "hafte": "हफ्ते",
    "hafta": "हफ्ता",
    "mahine": "महीनों",

    # 🔢 Numbers — word forms only (digits left ASCII for STEM safety)
    "ek": "एक",
    "do": "दो",
    "teen": "तीन",
    "chaar": "चार",
    "paanch": "पाँच",
    "chhah": "छह",
    "saat": "सात",
    "aath": "आठ",
    "nau": "नौ",
    "das": "दस",
    "gyaarah": "ग्यारह",
    "baarah": "बारह",
    "terah": "तेरह",
    "chaudah": "चौदह",
    "pandrah": "पंद्रह",
    "solah": "सोलह",
    "satrah": "सत्रह",
    "atharah": "अठारह",
    "unnees": "उन्नीस",
    "bees": "बीस",
    "ikkees": "इक्कीस",
    "baees": "बाईस",
    "teees": "तेईस",
    "chaubees": "चौबीस",
    "pachchees": "पच्चीस",
    "chhabbees": "छब्बीस",
    "sattais": "सत्ताईस",
    "atthais": "अट्ठाईस",
    "untees": "उनतीस",
    "tees": "तीस",
    "iktees": "इकतीस",
    "chalees": "चालीस",
    "pachaas": "पचास",
    "saath": "साठ",
    "sattar": "सत्तर",
    "assi": "अस्सी",
    "nabbe": "नब्बे",
    "sau": "सौ",
    "hajaar": "हज़ार",
    "do hajaar": "दो हज़ार",

    # 📅 Days
    "somvar": "सोमवार",
    "mangalvar": "मंगलवार",
    "budhvar": "बुधवार",
    "guruvar": "गुरुवार",
    "shukravar": "शुक्रवार",
    "shanivar": "शनिवार",
    "ravivar": "रविवार",

    # 💬 Questions & Grammar
    "kya": "क्या",
    "hai": "है",
    "kaisa": "कैसा",
    "kaisi": "कैसी",
    "kaun": "कौन",
    "kab": "कब",
    "kahan": "कहाँ",
    "kaise": "कैसे",
    "kyun": "क्यों",
    "ka": "का",
    "ki": "की",
    "ke": "के",

    # 📖 Wiki Queries
    "kaun hai": "क्या है",
    "kya hai": "क्या है",
    "hai kya": "क्या है",
    "kya aap jante hain": "क्या है",
    "search": "खोजो",
    "search karo": "खोजो",
    "khojo": "खोजो",
    "dikhaiye": "दिखाइए",
    "batao": "बताओ",
    "bataiye": "बताइए",
    "ke baare mein": "के बारे में",
    "ke bare mein": "के बारे में",
    "ka gyaan do": "जानकारी दो",
    "ka introduction": "परिचय दो",

    # 📰 News
    "news": "समाचार",
    "khabar": "खबर",
    "headlines": "मुख्य खबरें",

    # 📄 Notes & Memory
    "yaad": "याद",
    "note": "नोट",
    "likho": "लिखो",
    "padho": "पढ़ो",
    "padhna": "पढ़ना",
    "dikhao": "दिखाओ",
    "dikhaye": "दिखाएँ",
    "saare": "सारे",
    "purane": "पुराने",
    "sabhi": "सभी",
    "update": "अपडेट",
    "delete": "डिलीट",
    "hatado": "हटा दो",
    "badlo": "बदलो",
    "yaad rakh": "याद रखो",
    "bhool jao": "भूल जाओ",
    "yaad dilao": "याद दिलाओ",

    # 🔉 System Controls
    "brightness": "ब्राइटनेस",
    "brightness ko": "ब्राइटनेस को",
    "light": "ब्राइटनेस",
    "light ko": "ब्राइटनेस को",
    "roshni": "ब्राइटनेस",
    "roshni ko": "ब्राइटनेस को",

    "volume": "वॉल्यूम",
    "volume ko": "वॉल्यूम को",
    "awaaz": "वॉल्यूम",
    "awaaz ko": "वॉल्यूम को",
    "awaz": "वॉल्यूम",
    "awaz ko": "वॉल्यूम को",

    "kam": "कम",
    "zyada": "ज़्यादा",
    "badhao": "बढ़ाओ",
    "ghatao": "घटाओ",
    "band": "बंद",
    "band karo": "बंद करो",
    "chalu": "चालू",
    "restart": "पुनःचालू",
    "shutdown": "बंद करो",

    # 🔔 Alarms & Reminders
    "alarm": "अलार्म",
    "set": "सेट",
    "reminder": "रिमाइंडर",
    "samay pe": "समय पे",
    "alarm lagaao": "अलार्म लगाओ",
    "reminder lagaao": "रिमाइंडर लगाओ",

    # 🗣️ Commands & QA
    "suno": "सुनो",
    "sunna": "सुनना",
    "bolo": "बोलो",
    "command": "कमांड",
    "jawab": "जवाब",
    "question": "प्रश्न",
    "answer": "उत्तर",

    # 🙏 Apologies & Errors
    "maaf kijiye": "माफ़ कीजिए",
    "maaf karo": "माफ़ करो",
    "maafi chahta hoon": "माफ़ी चाहता हूँ",
    "samajh nahi paaya": "समझ नहीं पाया",
    "samajh nahi aaya": "समझ नहीं आया",
    "phir se kahiye": "फिर से कहिए",
    "dobara boliye": "दोबारा बोलिए",
    "repeat karo": "फिर से कहिए",
    "kya aap dobara kahenge": "क्या आप दोबारा कहेंगे",
    "galat samjha": "गलत समझा",
    "command clear nahi hai": "कमांड स्पष्ट नहीं है",

    # 🎉 Holidays & Festivals
    "tyohar": "त्योहार",
    "tyohar kab hai": "त्योहार कब है",
    "chutti": "छुट्टी",
    "festival": "त्योहार",
    "tyohar kab": "त्योहार कब",
    "chhutti": "छुट्टी",
    "festival kab hai": "त्योहार कब है",
    "holiday kab hai": "छुट्टी कब है",

    # 🎨 Colors
    "lal": "लाल",
    "neela": "नीला",
    "peela": "पीला",
    "hara": "हरा",
    "kaala": "काला",
    "safed": "सफ़ेद",
    "gulaabi": "गुलाबी",
    "bhura": "भूरा",
    "red": "लाल",
    "blue": "नीला",
    "yellow": "पीला",
    "green": "हरा",
    "black": "काला",
    "white": "सफ़ेद",
    "pink": "गुलाबी",
    "brown": "भूरा",

    # ➕ Math & Symbolic Keywords
    "ganit": "गणित",
    "ganitik": "गणितीय",
    "calculation": "गणना",
    "ganana": "गणना",
    "solve karo": "हल करो",
    "hal karo": "हल करो",
    "solution do": "हल दो",
    "ank": "अंक",
    "samasya": "समस्या",
    "samasya ka hal": "समस्या का हल",
    "samaikaran": "समीकरण",
    "equation": "समीकरण",
    "samikaran": "समीकरण",
    "paribhashit": "परिभाषित",
    "pratyek": "प्रत्येक",
    "samasya ko": "समस्या को",

    # 🔁 Matrix Operations
    "matrix": "मैट्रिक्स",
    "matrix inverse": "मैट्रिक्स इनवर्स",
    "matrix ka transpose": "मैट्रिक्स का ट्रांसपोज़",
    "transpose of matrix": "मैट्रिक्स का ट्रांसपोज़",
    "matrix transpose": "मैट्रिक्स का ट्रांसपोज़",
    "matrix determinant": "मैट्रिक्स डिटरमिनेंट",
    "determinant of matrix": "मैट्रिक्स डिटरमिनेंट",
    "matrix ka gunan": "मैट्रिक्स का गुणन",
    "matrix ko guna karo": "मैट्रिक्स का गुणन करो",
    "matrix multiplication": "मैट्रिक्स गुणन",
    "cofactor": "कोफैक्टर",
    "adjugate": "एडजुगेट",
    "inverse": "इनवर्स",
    "transpose": "ट्रांसपोज़",

    # 📊 Plotting Related
    "plot": "ग्राफ़",
    "graph": "ग्राफ़",
    "draw": "चित्रित",
    "rekha banaiye": "रेखा बनाईए",
    "chitr banao": "चित्र बनाओ",
    "y barabar": "y =",
    "x ke saman": "x =",
    "ankon ka plot": "अंकों का ग्राफ़",
    "data ka graph": "डेटा का ग्राफ़",

    # 🔢 Functions
    "gunan": "गुणन",
    "bhag": "भाग",
    "jod": "जोड़",
    "ghatao": "घटाओ",
    "antar karo": "घटाओ",
    "jod do": "जोड़ दो",
    "divide karo": "भाग करो",
    "multiply karo": "गुणा करो",
    "integrate karo": "इंटीग्रेट करो",
    "integral": "इंटीग्रल",
    "derivative": "व्युत्पन्न",
    "differentiate": "व्युत्पन्न निकालो",
    "nikalo": "निकालो"
}


# 🧲 Physics (Hinglish → Hindi) — extended with common romanized spellings

PHYSICS_HINGLISH_MAP = {
    # — Mode / intent —
    "physics mode": "फिजिक्स मोड",
    "solve physics": "भौतिकी सवाल",
    "physics problem": "भौतिकी प्रश्न",
    "use physics": "भौतिकी",
    "bhoutiki": "भौतिकी",
    "fiziks": "फिजिक्स",

    # — Kinematics / projectile —
    "projectile": "прक्षेप्य",
    "projectile motion": "प्रक्षेप्य गति",
    "time of flight": "उड़ान का समय",
    "maximum height": "अधिकतम ऊँचाई",
    "max height": "अधिकतम ऊँचाई",
    "projectile range": "परास",
    "range of projectile": "परास",
    "initial velocity": "प्रारंभिक वेग",
    "final velocity": "अंतिम वेग",
    "displacement": "विस्थापन",
    "acceleration": "त्वरण",

    # — Rotation / circular —
    "angular velocity": "कोणीय वेग",
    "angular acceleration": "कोणीय त्वरण",
    "torque": "आघूर्ण",
    "moment of inertia": "जड़त्व आघूर्ण",

    # — SHM —
    "simple harmonic motion": "सरल आवर्त गति",
    "spring constant": "स्प्रिंग स्थिरांक",

    # — Optics / waves —
    "refraction": "अपवर्तन",
    "reflection": "परावर्तन",
    "dispersion": "विक्षेपण",
    "total internal reflection": "पूर्ण आंतरिक परावर्तन",
    "critical angle": "क्रांतिक कोण",
    "wavelength": "तरंगदैर्ध्य",
    "frequency": "आवृत्ति",
    "rayleigh scattering": "रेली प्रकीर्णन",

    # — Electricity & magnetism —
    "ohms law": "ओम का नियम",
    "ohm law": "ओम का नियम",
    "ohm's law": "ओम का नियम",
    "newtons second law": "न्यूटन का दूसरा नियम",
    "newton second law": "न्यूटन का दूसरा नियम",
    "newton's second law": "न्यूटन का दूसरा नियम",
    "magnetic field": "चुंबकीय क्षेत्र",
    "magnetic flux": "चुंबकीय फ्लक्स",
    "capacitance": "धारिता",
    "inductance": "इंडक्टेंस",
    "impedance": "इम्पीडेंस",

    # — Fluids —
    "density": "घनत्व",
    "viscosity": "श्यानता",
    "buoyant force": "उत्प्लावन बल",

    # — Gravitation / constants —
    "escape velocity": "पलायन वेग",
    "gravitational field": "गुरुत्वाकर्षण क्षेत्र",
    "acceleration due to gravity": "गुरुत्वजनित त्वरण",
    "speed of light": "प्रकाश का वेग",
    "value of g": "g का मान",

    # — Proportionality / scaling phrases (for quick-facts) —
    "proportional to": "अनुपाती",
    "inversely proportional": "व्युत्क्रमानुपाती",
    "depends on": "निर्भर करता है",
    "what happens to": "क्या होगा",
    "double": "दोगुना",
    "doubles": "दोगुना",
    "triple": "तीन गुना",
    "triples": "तीन गुना",
    "quadruple": "चार गुना",
    "quadruples": "चार गुना",
    "half": "आधा",
    "halved": "आधा",
    "increased by": "बढ़ाकर",
    "decreased by": "घटाकर",
    "reduced to": "घटाकर",
    "percent": "प्रतिशत",
    "times": "गुना",
    "fold": "गुना",
}

# 🧲 Physics — romanized Hindi → Hindi (ultra-common colloquial spellings)
PHYSICS_ROMAN_HI_MAP = {
    # Optics / waves
    "apavartan": "अपवर्तन",
    "paravartan": "परावर्तन",
    "vikshepan": "विक्षेपण",
    "rayleigh prakeernan": "रेली प्रकीर्णन",
    "religh prakeernan": "रेली प्रकीर्णन",
    "reli prakeernan": "रेली प्रकीर्णन",
    "poorn aantarik paravartan": "पूर्ण आंतरिक परावर्तन",
    "poorn antarik paravartan": "पूर्ण आंतरिक परावर्तन",
    "purn antarik paravartan": "पूर्ण आंतरिक परावर्तन",
    "kritik kon": "क्रांतिक कोण",
    "krantik kon": "क्रांतिक कोण",
    "tarangdairghya": "तरंगदैर्ध्य",
    "tarang dairghya": "तरंगदैर्ध्य",
    "tarang lambai": "तरंगदैर्ध्य",
    "avriti": "आवृत्ति",
    "aavriti": "आवृत्ति",
    "avrtti": "आवृत्ति",

    # Rotation / mechanics
    "koniya veg": "कोणीय वेग",
    "koneey veg": "कोणीय वेग",
    "koniya tvaran": "कोणीय त्वरण",
    "jadatva aghurn": "जड़त्व आघूर्ण",
    "aghurn": "आघूर्ण",

    # Fluids
    "ghanatva": "घनत्व",
    "ghantva": "घनत्व",
    "shyanata": "श्यानता",
    "sayanata": "श्यानता",
    "utplavan bal": "उत्प्लावन बल",
    "utplavan": "उत्प्लावन",

    # Circuits / EM
    "ohm ka niyam": "ओम का नियम",
    "om ka niyam": "ओम का नियम",
    "chumbakiya kshetra": "चुंबकीय क्षेत्र",
    "chumbakiy kshetra": "चुंबकीय क्षेत्र",
    "chumbakiya flux": "चुंबकीय फ्लक्स",
    "dharita": "धारिता",
    "pratibadha": "प्रतिबाधा",
    "pratirodh": "प्रतिरोध",
    "preritata": "इंडक्टेंस",

    # Gravitation / constants
    "gurutvakarshan": "गुरुत्वाकर्षण",
    "gurutva kshetra": "गुरुत्वाकर्षण क्षेत्र",
    "palayan veg": "पलायन वेग",
    "prakash ka veg": "प्रकाश का वेग",
    "roshni ki raftaar": "प्रकाश का वेग",
    "newton ka dusra niyam": "न्यूटन का दूसरा नियम",

    # SHM
    "saral aavart gati": "सरल आवर्त गति",
    "spring sthirank": "स्प्रिंग स्थिरांक",
}


# 🧪 Chemistry (Hinglish → Hindi) — safe for parsers (no unit/formula rewrites)
CHEM_HINGLISH_MAP = {
    # Core intents / tasks
    "molar mass": "मोलर द्रव्यमान",
    "molar mass nikaal": "मोलर द्रव्यमान निकाल",
    "molar mass nikalo": "मोलर द्रव्यमान निकालो",
    "percent composition": "प्रतिशत संरचना",
    "percentage composition": "प्रतिशत संरचना",
    "composition": "संरचना",
    "empirical formula": "अनुभवजन्य सूत्र",
    "molecular formula": "आणविक सूत्र",
    "limiting reagent": "सीमित अभिकारक",
    "limiting reactant": "सीमित अभिकारक",
    "excess reagent": "अधिशेष अभिकारक",
    "stoichiometry": "स्टॉइकियोमेट्री",
    "stoich": "स्टॉइकियोमेट्री",
    "molarity": "मोलरता",
    "molality": "मोललता",
    "normality": "नॉर्मैलिटी",
    "dilution": "दुर्बलीकरण",
    "concentration": "सांद्रता",
    "solution": "विलयन",
    "solute": "विलेय",
    "solvent": "विलेयक",
    "mixture": "मिश्रण",
    "mixing": "मिलाना",

    # Acid–base & pH
    "acid": "अम्ल",
    "base": "क्षार",
    "strong acid": "प्रबल अम्ल",
    "weak acid": "दुर्बल अम्ल",
    "strong base": "प्रबल क्षार",
    "weak base": "दुर्बल क्षार",
    "acidity": "अम्लता",
    "basicity": "क्षारता",
    "buffer": "बफ़र",
    "ph kitna hoga": "पीएच कितना होगा",
    "ph nikal do": "पीएच निकाल दो",
    "poh nikal do": "पीओएच निकाल दो",

    # Gas laws (keep formulas/symbols ASCII in user text)
    "gas law": "गैस नियम",
    "boyle law": "बॉयल का नियम",
    "charles law": "चार्ल्स का नियम",
    "gay lussac law": "गे-लुसैक का नियम",
    "gay-lussac law": "गे-लुसैक का नियम",
    "avogadro law": "एवोगाद्रो का नियम",
    "ideal gas": "आदर्श गैस",
    "gas constant": "गैस स्थिरांक",
    "universal gas constant": "सार्वभौमिक गैस स्थिरांक",

    # Physical/periodic properties
    "boiling point": "उबलने का तापमान",
    "melting point": "गलने का तापमान",
    "density": "घनत्व",
    "electronegativity": "विद्युत ऋणात्मकता",
    "ionization energy": "आयनन ऊर्जा",
    "electron affinity": "इलेक्ट्रॉन आकर्षण",
    "atomic number": "परमाणु संख्या",
    "atomic mass": "परमाणु द्रव्यमान",
    "atomic weight": "परमाणु भार",
    "electron configuration": "इलेक्ट्रॉन विन्यास",
    "oxidation state": "ऑक्सीकरण अवस्था",
    "valency": "संयोजकता",
    "valence": "संयोजकता",
    "lone pair": "एकाकी युग्म",
    "bond order": "बंध क्रम",

    # Periodic table groups & families
    "alkali metals": "क्षारीय धातुएँ",
    "alkaline earth metals": "क्षारीय मृदा धातुएँ",
    "halogens": "हैलोजन",
    "noble gases": "निष्क्रिय गैसें",
    "transition metals": "संक्रमण धातुएँ",
    "metalloids": "उपधातु",
    "lanthanides": "लैंथेनाइड",
    "actinides": "ऐक्टिनाइड",
    "period": "आवर्त",
    "group": "समूह",

    # Percent & concentration phrases
    "mass percent": "द्रव्यमान प्रतिशत",
    "weight percent": "भार प्रतिशत",
    "volume percent": "आयतन प्रतिशत",
    "parts per million": "पीपीएम",
    "ppm": "पीपीएम",

    # Common user phrasings
    "moles nikaal do": "मोल निकाल दो",
    "moles nikalo": "मोल निकालो",
    "grams of": "ग्राम का",
    "find composition": "संरचना निकालो",
    "show steps": "कदम दिखाओ",
    "more detail": "और विवरण",

    # --- Numbers + common units ---
    "ek gram": "1 ग्राम",
    "do gram": "2 ग्राम",
    "teen gram": "3 ग्राम",
    "chaar gram": "4 ग्राम",
    "paanch gram": "5 ग्राम",
    "che gram": "6 ग्राम",
    "chhah gram": "6 ग्राम",
    "saat gram": "7 ग्राम",
    "aath gram": "8 ग्राम",
    "nau gram": "9 ग्राम",
    "das gram": "10 ग्राम",
    "gyaarah gram": "11 ग्राम",
    "baarah gram": "12 ग्राम",
    "terah gram": "13 ग्राम",
    "chaudah gram": "14 ग्राम",
    "pandrah gram": "15 ग्राम",
    "solah gram": "16 ग्राम",
    "satrah gram": "17 ग्राम",
    "atharah gram": "18 ग्राम",
    "unnees gram": "19 ग्राम",
    "bees gram": "20 ग्राम",
    "ikkees gram": "21 ग्राम",
    "baees gram": "22 ग्राम",
    "teees gram": "23 ग्राम",
    "chaubees gram": "24 ग्राम",
    "pachees gram": "25 ग्राम",
    "chhabbees gram": "26 ग्राम",
    "sattaees gram": "27 ग्राम",
    "athhaees gram": "28 ग्राम",
    "untees gram": "29 ग्राम",
    "tees gram": "30 ग्राम",
    "chaalees gram": "40 ग्राम",
    "chalees gram": "40 ग्राम",
    "pachaas gram": "50 ग्राम",
    "saath gram": "60 ग्राम",
    "sattar gram": "70 ग्राम",
    "assi gram": "80 ग्राम",
    "nabbe gram": "90 ग्राम",
    "sau gram": "100 ग्राम",

    # --- Moles ---
    "ek mol": "1 मोल",
    "do mol": "2 मोल",
    "teen mol": "3 मोल",
    "pandrah mol": "15 मोल",
    "unnees mol": "19 मोल",

    # --- Liters ---
    "ek litre": "1 लीटर",
    "do litre": "2 लीटर",
    "teen litre": "3 लीटर",
    "pandrah litre": "15 लीटर",
    "unnees litre": "19 लीटर",

    # --- Milliliters ---
    "ek ml": "1 mL",
    "do ml": "2 mL",
    "teen ml": "3 mL",
    "pandrah ml": "15 mL",
    "unnees ml": "19 mL",

    # --- Millimoles ---
    "ek mmol": "1 mmol",
    "do mmol": "2 mmol",
    "teen mmol": "3 mmol",
    "pandrah mmol": "15 mmol",
    "unnees mmol": "19 mmol"
}

# 🔗 Merge: physics first (intent/colloquial), then chemistry
hinglish_map.update(PHYSICS_HINGLISH_MAP)
hinglish_map.update(PHYSICS_ROMAN_HI_MAP)
hinglish_map.update(CHEM_HINGLISH_MAP)


# 🔧 Precompile patterns (longest keys first)
_PATTERNS = [
    (re.compile(r'\b' + re.escape(k) + r'\b'), v)
    for k, v in sorted(hinglish_map.items(), key=lambda kv: len(kv[0]), reverse=True)
]


def normalize_hinglish(command: str) -> str:
    """Normalize common Hinglish phrases to Hindi (Devanagari).
    - Leaves digits, units, formulas, and symbols untouched.
    - Longest-first replacement avoids partial overshadowing.
    """
    text = command.lower()
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text
