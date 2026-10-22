"""Disease names and simple advice in English and Hindi.

Owner: Member B

The model's raw labels (for example "Corn___Common_Rust") are matched by keywords,
so the code keeps working even if the exact spelling of a label differs.
Run `python -m scripts.download_model` to print every label and check that each one
matches an entry below.

DATA YOU SHOULD CHECK: the advice is general and safe on purpose. If possible, show it
to a teacher from agriculture or your nearest Krishi Vigyan Kendra and adjust the words.
"""
import re

EXPERT = {
    "en": "Before using any chemical, ask your nearest Krishi Vigyan Kendra (KVK) or call the "
          "Kisan Call Centre: 1800-180-1551 (toll-free).",
    "hi": "कोई भी दवा इस्तेमाल करने से पहले नज़दीकी कृषि विज्ञान केंद्र (KVK) से पूछें या "
          "किसान कॉल सेंटर पर कॉल करें: 1800-180-1551 (टोल-फ़्री)।",
}

CROPS = {
    "corn": {"en": "Maize (corn)", "hi": "मक्का"},
    "potato": {"en": "Potato", "hi": "आलू"},
    "rice": {"en": "Rice (paddy)", "hi": "धान"},
    "wheat": {"en": "Wheat", "hi": "गेहूँ"},
}

HEALTHY_ADVICE = {
    "en": ["The app did not detect a disease on this leaf.",
           "Keep checking a few leaves every week, especially after rain."],
    "hi": ["ऐप को इस पत्ती पर कोई रोग नहीं दिखा।",
           "हर हफ़्ते कुछ पत्तियाँ जाँचते रहें, खासकर बारिश के बाद।"],
}

UNSURE = {
    "id": "unsure",
    "crop": None,
    "name": {"en": "Not sure", "hi": "पक्का नहीं"},
    "healthy": False,
    "advice": {
        "en": ["We could not recognise a crop leaf in this photo with enough confidence.",
               "Take a clear, close photo of one leaf in daylight, filling most of the frame.",
               "This app checks maize, potato, rice and wheat leaves."],
        "hi": ["इस फोटो में हम फसल की पत्ती को भरोसे के साथ पहचान नहीं पाए।",
               "दिन की रोशनी में एक पत्ती की साफ़, पास से फोटो लें, जिसमें पत्ती ज़्यादातर फ्रेम भरे।",
               "यह ऐप मक्का, आलू, धान और गेहूँ की पत्तियाँ जाँचता है।"],
    },
    "management": {
        "immediate_steps": {"en": ["Do not spray or apply a treatment based only on this uncertain result.", "Take well-focused photographs of several leaves and check the whole field for symptoms."],
                            "hi": ["इस अनिश्चित परिणाम के आधार पर दवा का छिड़काव या उपचार न करें।", "कई पत्तियों की साफ तस्वीर लें और पूरे खेत में लक्षण जाँचें।"]},
        "prevention": {"en": ["Use locally recommended seed or planting material, follow crop rotation where appropriate, and base fertiliser on soil testing.", "Avoid unnecessary pesticide use; follow integrated pest management and local agricultural advice."],
                       "hi": ["स्थानीय अनुशंसित बीज/रोपण सामग्री लें, जहाँ उचित हो फसल चक्र अपनाएँ और मिट्टी जाँच के अनुसार खाद दें।", "अनावश्यक कीटनाशक न डालें; समेकित कीट प्रबंधन और स्थानीय कृषि सलाह अपनाएँ।"]},
        "monitoring": {"en": ["Inspect several plants across different parts of the field and check whether symptoms are spreading over the next 2–3 days."],
                       "hi": ["खेत के अलग-अलग हिस्सों में कई पौधे जाँचें और अगले 2–3 दिन में लक्षण फैल रहे हैं या नहीं देखें।"]},
        "crop_care": {"en": ["This photo was not confidently classified, so crop-specific care cannot be selected safely. Identify the crop or ask KVK for help.", "Keep records of crop, sowing date, recent weather, symptoms and any treatments already applied."],
                       "hi": ["फोटो की पक्की पहचान नहीं हुई, इसलिए सुरक्षित तरीके से फसल-विशेष सलाह नहीं चुनी जा सकती। फसल की पहचान करें या KVK से पूछें।", "फसल, बुवाई की तारीख, हाल का मौसम, लक्षण और पहले किए गए उपचार का रिकॉर्ड रखें।"]},
        "escalate_if": {"en": ["Contact your local KVK or agriculture officer if symptoms spread, many plants are affected, or the crop is near flowering or grain filling."],
                         "hi": ["लक्षण फैलें, कई पौधे प्रभावित हों या फसल फूलने/दाना भरने की अवस्था में हो तो स्थानीय KVK या कृषि अधिकारी से संपर्क करें।"]},
        "chemical_safety": {"en": ["The model does not prescribe chemical products or doses. Use a pesticide only after crop-specific advice from a qualified local adviser and follow its registered label, protective equipment and pre-harvest interval."],
                            "hi": ["यह मॉडल रसायन या मात्रा नहीं बताता। योग्य स्थानीय विशेषज्ञ की फसल-विशेष सलाह के बाद ही दवा लें और पंजीकृत लेबल, सुरक्षा उपकरण तथा कटाई-पूर्व अंतराल का पालन करें।"]},
    },
    "sources": [
        {"label": "ICAR crop advisories", "label_hi": "ICAR फसल सलाह", "url": "https://icar.org.in/"},
        {"label": "ICAR-CRIDA district contingency plans", "label_hi": "ICAR-CRIDA ज़िला आकस्मिक फसल योजनाएँ", "url": "https://www.icar-crida.res.in/Crop_Contingency_Plan.html"},
        {"label": "Kisan Call Centre", "label_hi": "किसान कॉल सेंटर", "url": "https://mkisan.gov.in/"},
    ],
}

DISEASES = {
    "corn_common_rust": {
        "crop": "corn", "name": {"en": "Common rust", "hi": "रतुआ (गेरुई) रोग"},
        "advice": {
            "en": ["Small reddish-brown powdery spots on both sides of the leaf.",
                   "Next season, sow rust-resistant hybrids and remove maize plants that grow on their own.",
                   "If many leaves are covered before tasselling, a fungicide spray may be needed - ask an agriculture officer which one."],
            "hi": ["पत्तियों के दोनों तरफ छोटे लाल-भूरे, पाउडर जैसे धब्बे।",
                   "अगले मौसम में रतुआ-रोधी किस्में बोएँ और अपने आप उगे मक्का के पौधे हटा दें।",
                   "अगर झंडे (नर मंजरी) निकलने से पहले बहुत सी पत्तियाँ प्रभावित हों, तो फफूंदनाशक छिड़काव की ज़रूरत हो सकती है - कौन सी दवा, यह कृषि अधिकारी से पूछें।"],
        },
    },
    "corn_gray_leaf_spot": {
        "crop": "corn", "name": {"en": "Gray leaf spot", "hi": "धूसर पत्ती धब्बा रोग"},
        "advice": {
            "en": ["Long, narrow grey-brown rectangular spots between the leaf veins.",
                   "The fungus lives on old crop remains - remove them or plough them in, and grow a different crop next time.",
                   "Use tolerant hybrids; ask an agriculture officer before spraying."],
            "hi": ["पत्ती की नसों के बीच लंबे, पतले, धूसर-भूरे आयताकार धब्बे।",
                   "यह फफूंद पुराने फसल अवशेषों पर रहती है - अवशेष हटाएँ या जुताई करके मिट्टी में दबाएँ, और अगली बार दूसरी फसल लगाएँ।",
                   "सहनशील किस्में लगाएँ; छिड़काव से पहले कृषि अधिकारी से सलाह लें।"],
        },
    },
    "corn_leaf_blight": {
        "crop": "corn", "name": {"en": "Leaf blight", "hi": "पत्ती झुलसा रोग"},
        "advice": {
            "en": ["Long, cigar-shaped grey-green to tan patches on the leaves.",
                   "Rotate crops, clear old crop remains and use resistant hybrids.",
                   "Avoid very dense sowing so the leaves dry faster."],
            "hi": ["पत्तियों पर लंबे, सिगार जैसे धूसर-हरे से भूरे धब्बे।",
                   "फसल चक्र अपनाएँ, पुराने फसल अवशेष हटाएँ और रोग-रोधी किस्में लगाएँ।",
                   "बहुत घनी बुवाई न करें ताकि पत्तियाँ जल्दी सूखें।"],
        },
    },
    "potato_early_blight": {
        "crop": "potato", "name": {"en": "Early blight", "hi": "अगेती झुलसा रोग"},
        "advice": {
            "en": ["Brown spots with rings like a target, usually on older lower leaves first.",
                   "Remove badly affected leaves and give balanced fertiliser - weak plants get this disease more.",
                   "Water at the base of the plant, not over the leaves."],
            "hi": ["निशाने जैसी गोल छल्लेदार भूरी चित्तियाँ, ज़्यादातर पहले नीचे की पुरानी पत्तियों पर।",
                   "ज़्यादा प्रभावित पत्तियाँ हटा दें और संतुलित खाद दें - कमज़ोर पौधों में यह रोग ज़्यादा लगता है।",
                   "पानी पत्तियों पर नहीं, पौधे की जड़ के पास दें।"],
        },
    },
    "potato_late_blight": {
        "crop": "potato", "name": {"en": "Late blight", "hi": "पछेती झुलसा रोग"},
        "advice": {
            "en": ["Dark, water-soaked patches that spread fast in cool, cloudy, wet weather; white mould may show under the leaf.",
                   "Act quickly: pull out and destroy infected plants - do not leave them in the field or the compost pit.",
                   "Avoid watering from above and tell nearby farmers - it spreads with the wind."],
            "hi": ["ठंडे, बादल वाले, नम मौसम में तेज़ी से फैलने वाले गहरे, पानी से भीगे जैसे धब्बे; पत्ती के नीचे सफ़ेद फफूंद दिख सकती है।",
                   "तुरंत कदम उठाएँ: संक्रमित पौधे उखाड़कर नष्ट करें - खेत में या खाद के गड्ढे में न छोड़ें।",
                   "ऊपर से सिंचाई न करें और आसपास के किसानों को बताएँ - यह रोग हवा से फैलता है।"],
        },
    },
    "rice_brown_spot": {
        "crop": "rice", "name": {"en": "Brown spot", "hi": "भूरा धब्बा रोग"},
        "advice": {
            "en": ["Small oval brown spots with a grey centre on the leaves.",
                   "It is common in weak or poor soil - get a soil test and give balanced fertiliser, especially potash.",
                   "Use healthy, treated seed for the next crop."],
            "hi": ["पत्तियों पर बीच में धूसर रंग वाले छोटे, अंडाकार भूरे धब्बे।",
                   "यह कमज़ोर या कम उपजाऊ मिट्टी में ज़्यादा होता है - मिट्टी की जाँच कराएँ और संतुलित खाद, खासकर पोटाश, दें।",
                   "अगली फसल के लिए स्वस्थ और उपचारित बीज लें।"],
        },
    },
    "rice_leaf_blast": {
        "crop": "rice", "name": {"en": "Leaf blast", "hi": "झोंका (ब्लास्ट) रोग"},
        "advice": {
            "en": ["Eye- or boat-shaped spots with grey centres and brown edges.",
                   "Do not add extra urea (nitrogen) while the disease is active.",
                   "Next season use blast-resistant varieties; ask an agriculture officer about a fungicide spray."],
            "hi": ["आँख या नाव के आकार के धब्बे - बीच में धूसर और किनारे भूरे।",
                   "रोग के दौरान अतिरिक्त यूरिया (नाइट्रोजन) न डालें।",
                   "अगले मौसम में ब्लास्ट-रोधी किस्में लगाएँ; फफूंदनाशक छिड़काव के बारे में कृषि अधिकारी से पूछें।"],
        },
    },
    "rice_hispa": {
        "crop": "rice", "name": {"en": "Hispa (insect damage)", "hi": "हिस्पा कीट"},
        "advice": {
            "en": ["A small insect (the hispa beetle) scrapes the leaf, leaving white streaks or patches.",
                   "In the nursery or young crop, cut and destroy the damaged leaf tips.",
                   "Avoid too much nitrogen; ask an agriculture officer whether an insecticide is needed."],
            "hi": ["एक छोटा कीट (हिस्पा भृंग) पत्ती को खुरचता है, जिससे सफ़ेद धारियाँ या धब्बे बनते हैं।",
                   "नर्सरी या छोटी फसल में प्रभावित पत्तियों के सिरे काटकर नष्ट करें।",
                   "ज़्यादा नाइट्रोजन न डालें; कीटनाशक की ज़रूरत है या नहीं, कृषि अधिकारी से पूछें।"],
        },
    },
    "wheat_brown_rust": {
        "crop": "wheat", "name": {"en": "Brown rust", "hi": "भूरा रतुआ"},
        "advice": {
            "en": ["Small orange-brown powdery spots scattered on the leaves.",
                   "Sow rust-resistant varieties recommended for your area and avoid very late sowing.",
                   "If it spreads before the grain fills, ask an agriculture officer about a fungicide spray."],
            "hi": ["पत्तियों पर बिखरे हुए छोटे नारंगी-भूरे, पाउडर जैसे धब्बे।",
                   "अपने क्षेत्र के लिए सुझाई गई रतुआ-रोधी किस्में बोएँ और बहुत देर से बुवाई न करें।",
                   "अगर दाना भरने से पहले रोग फैल रहा हो, तो फफूंदनाशक छिड़काव के बारे में कृषि अधिकारी से पूछें।"],
        },
    },
    "wheat_yellow_rust": {
        "crop": "wheat", "name": {"en": "Yellow rust", "hi": "पीला रतुआ"},
        "advice": {
            "en": ["Yellow powdery stripes along the leaf veins, common in cool weather in north India.",
                   "Report it quickly to an agriculture officer - yellow rust spreads fast from field to field.",
                   "Sow resistant varieties next season; ask the officer about a fungicide spray now."],
            "hi": ["पत्ती की नसों के साथ पीली पाउडर जैसी धारियाँ, उत्तर भारत में ठंडे मौसम में आम।",
                   "कृषि अधिकारी को तुरंत बताएँ - पीला रतुआ एक खेत से दूसरे खेत में तेज़ी से फैलता है।",
                   "अगले मौसम में रोग-रोधी किस्में बोएँ; अभी फफूंदनाशक छिड़काव के बारे में अधिकारी से पूछें।"],
        },
    },
}

# Healthy entries for every crop.
for _crop in CROPS:
    DISEASES[f"{_crop}_healthy"] = {
        "crop": _crop, "name": {"en": "Healthy", "hi": "स्वस्थ"}, "advice": HEALTHY_ADVICE,
    }

# Keywords that identify a disease inside each crop, checked in order.
_RULES = {
    "corn": [("gray", "corn_gray_leaf_spot"), ("grey", "corn_gray_leaf_spot"),
             ("cercospora", "corn_gray_leaf_spot"), ("rust", "corn_common_rust"),
             ("blight", "corn_leaf_blight")],
    "potato": [("early", "potato_early_blight"), ("late", "potato_late_blight")],
    "rice": [("blast", "rice_leaf_blast"), ("brown", "rice_brown_spot"), ("hispa", "rice_hispa")],
    "wheat": [("yellow", "wheat_yellow_rust"), ("stripe", "wheat_yellow_rust"),
              ("brown", "wheat_brown_rust"), ("leaf rust", "wheat_brown_rust")],
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z]+", " ", str(text).lower()).strip()


def match_label(label: str):
    """Turn a raw model label into one of our ids, 'invalid', or None if unknown."""
    t = _norm(label)
    if "invalid" in t or "background" in t or "not a leaf" in t:
        return "invalid"
    if "corn" in t or "maize" in t:
        crop = "corn"
    elif "potato" in t:
        crop = "potato"
    elif "rice" in t or "paddy" in t:
        crop = "rice"
    elif "wheat" in t:
        crop = "wheat"
    else:
        return None
    if "healthy" in t:
        return f"{crop}_healthy"
    for keyword, disease_id in _RULES[crop]:
        if keyword in t:
            return disease_id
    return None



# Crop-wide good practices are shown for both healthy and diseased results. They are
# intentionally practical and conservative; no pesticide brand/dose is prescribed.
CROP_CARE = {
    "corn": {"en": [
        "Use a locally recommended hybrid and sow within the district's advised window.",
        "Base nitrogen, phosphorus and potassium on soil testing; split nitrogen according to local package of practices.",
        "Maintain recommended plant spacing and keep weeds controlled during early growth.",
        "Check whorls and leaf undersides weekly for fall armyworm, rust and leaf-blight symptoms.",
        "Avoid waterlogging; around flowering, check field moisture because water stress can reduce grain set.",
        "Harvest at suitable grain moisture and dry safely before storage."],
      "hi": [
        "जिले के लिए सुझाई गई संकर किस्म चुनें और सलाहित समय पर बुवाई करें।",
        "नाइट्रोजन, फॉस्फोरस और पोटाश की मात्रा मिट्टी जाँच के आधार पर तय करें; नाइट्रोजन स्थानीय कृषि पद्धति के अनुसार बाँटकर दें।",
        "अनुशंसित दूरी रखें और शुरुआती बढ़वार में खरपतवार नियंत्रित करें।",
        "हर सप्ताह पत्तियों और भुट्टे के पास फॉल आर्मीवर्म, रतुआ और झुलसा के लक्षण देखें।",
        "खेत में जलभराव न होने दें; फूल आने के समय नमी जाँचें क्योंकि पानी की कमी से दाना कम बन सकता है।",
        "उचित नमी पर कटाई करें और भंडारण से पहले सुरक्षित रूप से सुखाएँ।"]},
    "potato": {"en": [
        "Use certified, healthy seed tubers and a variety recommended for the local season.",
        "Rotate away from potato and other solanaceous crops where practical; do not leave infected tubers or cull piles in the field.",
        "Keep ridges and drainage in good condition; avoid long periods of leaf wetness where possible.",
        "Apply nutrients according to soil testing and crop stage; avoid imbalanced nitrogen.",
        "Scout lower leaves regularly for early-blight rings and wet-weather late-blight lesions.",
        "Store only mature, undamaged tubers in a cool, ventilated, dark place appropriate to the intended use."],
      "hi": [
        "प्रमाणित, स्वस्थ बीज-कंद और स्थानीय मौसम के लिए अनुशंसित किस्म चुनें।",
        "जहाँ संभव हो आलू और अन्य सोलेनेसी फसलों के बीच फसल चक्र अपनाएँ; संक्रमित कंद या खराब कंदों के ढेर खेत में न छोड़ें।",
        "मेड़ और जल निकासी ठीक रखें; पत्तियों को लंबे समय तक गीला रहने से बचाएँ।",
        "मिट्टी जाँच और फसल अवस्था के अनुसार पोषक तत्व दें; नाइट्रोजन असंतुलित न रखें।",
        "नीचे की पत्तियों पर अगेती झुलसा के छल्लेदार धब्बे तथा नम मौसम में पछेती झुलसा के लक्षण देखें।",
        "केवल परिपक्व और बिना चोट वाले कंदों को उपयुक्त ठंडी, हवादार और अँधेरी जगह पर रखें।"]},
    "rice": {"en": [
        "Use certified seed and locally recommended varieties; follow the advised nursery/direct-seeding window.",
        "Use soil-test-based nutrients and avoid excessive nitrogen, especially where blast is present.",
        "Manage water according to the local rice system; do not apply a generic ET estimate as a paddy flooding schedule.",
        "Scout weekly for blast, brown spot, hispa, stem borer and other locally important pests.",
        "Maintain weed control and field drainage; avoid unnecessary prolonged standing water where local practice does not require it.",
        "Harvest near the locally recommended maturity and dry grain to the safe moisture level for storage."],
      "hi": [
        "प्रमाणित बीज और स्थानीय अनुशंसित किस्म लें; नर्सरी या सीधी बुवाई का सही समय अपनाएँ।",
        "मिट्टी जाँच के आधार पर खाद दें और विशेषकर ब्लास्ट रोग में अतिरिक्त नाइट्रोजन से बचें।",
        "स्थानीय धान पद्धति के अनुसार पानी सँभालें; सामान्य ET अनुमान को धान में पानी भरने की पूरी समय-सारणी न मानें।",
        "हर सप्ताह ब्लास्ट, भूरा धब्बा, हिस्पा, तना छेदक और स्थानीय कीटों की जाँच करें।",
        "खरपतवार और जल निकासी सँभालें; स्थानीय पद्धति में आवश्यक न हो तो अनावश्यक लंबे समय तक पानी न भरें।",
        "स्थानीय सलाह के अनुसार परिपक्वता पर कटाई करें और भंडारण के सुरक्षित स्तर तक अनाज सुखाएँ।"]},
    "wheat": {"en": [
        "Choose a locally recommended, disease-resistant variety and sow in the advised window.",
        "Use seed rate and row spacing recommended for the variety and sowing date.",
        "Apply nutrients based on soil test and local recommendations; split nitrogen where advised.",
        "Check leaves weekly for yellow or brown rust, especially during cool, humid weather.",
        "Schedule irrigation around critical stages using field moisture and the local advisory, not forecast alone.",
        "Harvest at maturity and dry grain properly before storing."],
      "hi": [
        "स्थानीय रूप से अनुशंसित और रोग-सहनशील किस्म चुनें तथा सलाहित समय पर बुवाई करें।",
        "किस्म और बुवाई के समय के अनुसार बीज मात्रा और कतार दूरी रखें।",
        "मिट्टी जाँच तथा स्थानीय सलाह के अनुसार पोषक तत्व दें; जहाँ सलाह हो वहाँ नाइट्रोजन बाँटकर दें।",
        "ठंडे और नम मौसम में विशेष रूप से पत्तियों पर पीले या भूरे रतुआ के लक्षण हर सप्ताह देखें।",
        "महत्वपूर्ण अवस्थाओं में खेत की नमी और स्थानीय सलाह से सिंचाई तय करें, केवल मौसम पूर्वानुमान से नहीं।",
        "परिपक्वता पर कटाई करें और भंडारण से पहले अनाज अच्छी तरह सुखाएँ।"]},
}

DISEASE_MANAGEMENT = {
    "corn_common_rust": {
      "immediate": {"en": ["Inspect several plants in different parts of the field and note whether pustules are spreading onto upper leaves.", "Avoid moving infected plant debris between fields; ask a local officer to confirm if the field is heavily affected."], "hi": ["खेत के अलग-अलग हिस्सों में कई पौधे देखें और दर्ज करें कि धब्बे ऊपर की पत्तियों तक फैल रहे हैं या नहीं।", "संक्रमित अवशेष खेतों के बीच न ले जाएँ; अधिक रोग होने पर कृषि अधिकारी से पुष्टि कराएँ।"]},
      "prevention": {"en": ["Choose resistant/tolerant hybrids recommended for the district and remove volunteer maize where advised.", "Manage crop residues and avoid planting a susceptible hybrid repeatedly where rust is recurring."], "hi": ["जिले के लिए अनुशंसित रतुआ-सहनशील संकर चुनें और सलाह के अनुसार अपने आप उगे मक्का के पौधे हटाएँ।", "फसल अवशेष सँभालें और बार-बार रोग होने पर लगातार संवेदनशील संकर न लगाएँ।"]}},
    "corn_gray_leaf_spot": {
      "immediate": {"en": ["Mark affected patches and inspect whether rectangular lesions are spreading after humid weather.", "Avoid unnecessary overhead irrigation and seek field confirmation if lesions are increasing."], "hi": ["प्रभावित हिस्से चिन्हित करें और नम मौसम के बाद आयताकार धब्बों के फैलाव को देखें।", "अनावश्यक ऊपर से सिंचाई से बचें; धब्बे बढ़ने पर खेत में पुष्टि कराएँ।"]},
      "prevention": {"en": ["Use tolerant hybrids and rotate with a non-host crop where locally suitable.", "Manage infected residue according to local practice and use spacing that allows airflow."], "hi": ["सहनशील संकर चुनें और स्थानीय रूप से उपयुक्त गैर-मेज़बान फसल से चक्र बदलें।", "स्थानीय पद्धति के अनुसार संक्रमित अवशेष सँभालें और हवा आने-जाने लायक दूरी रखें।"]}},
    "corn_leaf_blight": {
      "immediate": {"en": ["Photograph symptoms on several leaves and check whether long lesions are expanding after rain.", "Keep records of the first date noticed and crop stage for an extension worker."], "hi": ["कई पत्तियों पर लक्षणों की फोटो लें और बारिश के बाद लंबे धब्बों का फैलाव देखें।", "पहली बार लक्षण दिखने की तारीख और फसल अवस्था लिखकर कृषि विशेषज्ञ को बताएँ।"]},
      "prevention": {"en": ["Use locally recommended tolerant hybrids and rotate crops.", "Manage residue and plant density based on local recommendations; do not spray without confirmed diagnosis."], "hi": ["स्थानीय रूप से अनुशंसित सहनशील संकर और फसल चक्र अपनाएँ।", "स्थानीय सलाह के अनुसार अवशेष और पौध दूरी सँभालें; पुष्टि के बिना छिड़काव न करें।"]}},
    "potato_early_blight": {
      "immediate": {"en": ["Inspect lower, older leaves for target-like rings; remove only severely affected material if this can be done without spreading it.", "Avoid unnecessary leaf wetting and reduce plant stress with balanced, soil-test-based nutrition."], "hi": ["नीचे की पुरानी पत्तियों पर निशाने जैसे छल्लेदार धब्बे देखें; फैलाव रोके बिना बहुत प्रभावित सामग्री ही हटाएँ।", "पत्तियाँ अनावश्यक गीली न करें और मिट्टी जाँच आधारित संतुलित पोषण से पौधे का तनाव घटाएँ।"]},
      "prevention": {"en": ["Use healthy seed tubers, rotate crops and avoid leaving potato debris or volunteer plants.", "Keep a regular scouting record, especially as the canopy closes."], "hi": ["स्वस्थ बीज-कंद लें, फसल चक्र अपनाएँ और आलू के अवशेष/अपने आप उगे पौधे न छोड़ें।", "विशेषकर पत्तियों का घना छत्र बनने पर नियमित निगरानी लिखें।"]}},
    "potato_late_blight": {
      "immediate": {"en": ["Treat this as urgent when dark water-soaked lesions spread quickly in cool, wet weather; contact KVK/agriculture staff promptly.", "Avoid carrying infected plants/tubers through healthy fields. Follow local guidance for safe disposal; do not feed infected tubers to livestock."], "hi": ["ठंडे, नम मौसम में गहरे पानी-भीगे धब्बे तेजी से फैलें तो इसे तात्कालिक मानें और तुरंत KVK/कृषि अधिकारी से संपर्क करें।", "संक्रमित पौधे/कंद स्वस्थ खेतों से होकर न ले जाएँ। सुरक्षित निपटान की स्थानीय सलाह मानें; संक्रमित कंद पशुओं को न खिलाएँ।"]},
      "prevention": {"en": ["Use certified seed, maintain drainage, scout frequently during cool humid periods and avoid unnecessary overhead watering.", "Ask an extension officer whether locally registered fungicide protection is warranted; follow the product label exactly."], "hi": ["प्रमाणित बीज लें, जल निकासी ठीक रखें, ठंडे-नम मौसम में बार-बार देखें और अनावश्यक ऊपर से पानी न दें।", "स्थानीय रूप से पंजीकृत फफूंदनाशक की आवश्यकता कृषि अधिकारी से पूछें और लेबल का ठीक पालन करें।"]}},
    "rice_brown_spot": {
      "immediate": {"en": ["Inspect multiple leaves and panicles; brown spot can be associated with crop stress, but the photo alone cannot establish the cause.", "Check soil health, nutrient balance and moisture management; do not add a nutrient blindly."], "hi": ["कई पत्तियाँ और बालियाँ देखें; भूरा धब्बा फसल तनाव से जुड़ सकता है, लेकिन केवल फोटो से कारण निश्चित नहीं होता।", "मिट्टी की सेहत, पोषक संतुलन और नमी जाँचें; बिना जाँच खाद न डालें।"]},
      "prevention": {"en": ["Use healthy seed and locally recommended seed treatment when prescribed; improve balanced nutrition based on soil test.", "Avoid moisture stress and maintain weed/crop-residue management according to local guidance."], "hi": ["स्वस्थ बीज लें और जहाँ सलाह हो वहाँ अनुशंसित बीज उपचार करें; मिट्टी जाँच के अनुसार संतुलित पोषण दें।", "नमी का तनाव न होने दें और स्थानीय सलाह से खरपतवार/अवशेष सँभालें।"]}},
    "rice_leaf_blast": {
      "immediate": {"en": ["Inspect neighbouring plants and check whether diamond-shaped lesions are increasing, especially after humid nights.", "Avoid excess nitrogen; consult KVK promptly if lesions spread or panicles begin showing symptoms."], "hi": ["पास के पौधों को देखें और नम रातों के बाद हीरे जैसे धब्बों के बढ़ने पर ध्यान दें।", "अतिरिक्त नाइट्रोजन न दें; धब्बे फैलें या बालियों पर लक्षण दिखें तो तुरंत KVK से सलाह लें।"]},
      "prevention": {"en": ["Use locally recommended resistant varieties, balanced split nitrogen and healthy seed.", "Scout at tillering, panicle initiation and heading; chemical choice and timing must be confirmed locally."], "hi": ["स्थानीय रूप से अनुशंसित रोग-सहनशील किस्म, संतुलित और बाँटकर नाइट्रोजन तथा स्वस्थ बीज अपनाएँ।", "कल्ले निकलने, बाली बनने और बालियाँ निकलने की अवस्था में जाँचें; दवा और समय स्थानीय विशेषज्ञ से तय करें।"]}},
    "rice_hispa": {
      "immediate": {"en": ["Look for white scraping streaks and beetles/larvae on affected leaves; inspect several rows before deciding how widespread it is.", "Remove a small number of badly damaged leaves or adults where practical; avoid broad pesticide use without a threshold-based local recommendation."], "hi": ["प्रभावित पत्तियों पर सफेद खुरची धारियाँ और भृंग/लार्वा देखें; फैलाव समझने के लिए कई कतारें जाँचें।", "जहाँ संभव हो थोड़ी संख्या में बहुत प्रभावित पत्तियाँ/भृंग हटाएँ; स्थानीय सलाह के बिना व्यापक कीटनाशक न डालें।"]},
      "prevention": {"en": ["Keep regular pest scouting, conserve beneficial insects and avoid excess nitrogen that creates overly lush growth.", "Ask an agriculture officer to confirm the pest and local action threshold before treatment."], "hi": ["नियमित कीट निगरानी करें, लाभकारी कीट बचाएँ और अत्यधिक नाइट्रोजन से बहुत कोमल बढ़वार न होने दें।", "उपचार से पहले कृषि अधिकारी से कीट और स्थानीय कार्रवाई सीमा की पुष्टि कराएँ।"]}},
    "wheat_brown_rust": {
      "immediate": {"en": ["Check multiple leaves and nearby fields for orange-brown pustules; record crop stage and spread.", "If rust is increasing before grain filling, contact local agriculture staff for a district-specific management recommendation."], "hi": ["कई पत्तियों और पास के खेतों में नारंगी-भूरे धब्बे देखें; फसल अवस्था और फैलाव लिखें।", "दाना भरने से पहले रतुआ बढ़ रहा हो तो जिले के अनुसार सलाह के लिए कृषि अधिकारी से संपर्क करें।"]},
      "prevention": {"en": ["Choose resistant varieties recommended for your zone and sow in the advised window.", "Scout regularly and avoid moving volunteer wheat/host material between fields."], "hi": ["अपने क्षेत्र के लिए अनुशंसित रोग-सहनशील किस्म और उचित बुवाई समय अपनाएँ।", "नियमित निगरानी करें और अपने आप उगे गेहूँ/मेज़बान पौधे खेतों में न फैलाएँ।"]}},
    "wheat_yellow_rust": {
      "immediate": {"en": ["Yellow powdery stripes along veins can spread quickly in cool, humid conditions. Scout neighbouring fields and report a suspected outbreak promptly to agriculture staff/KVK.", "If treatment is advised, use only a currently registered product for the crop and disease; follow the label, protective equipment and pre-harvest interval."], "hi": ["ठंडे-नम मौसम में नसों के साथ पीली पाउडर धारियाँ तेजी से फैल सकती हैं। आसपास के खेत देखें और संदेह होने पर तुरंत कृषि अधिकारी/KVK को बताएँ।", "उपचार की सलाह मिले तो गेहूँ और इस रोग के लिए वर्तमान में पंजीकृत उत्पाद ही लें; लेबल, सुरक्षा उपकरण और कटाई-पूर्व अंतराल मानें।"]},
      "prevention": {"en": ["Use resistant varieties recommended for your zone and monitor in cool weather after dew/rain.", "Do not wait for the whole field to turn yellow before seeking confirmation."], "hi": ["अपने क्षेत्र के लिए अनुशंसित रोग-सहनशील किस्म अपनाएँ और ओस/बारिश के बाद ठंडे मौसम में निगरानी करें।", "पूरे खेत के पीले होने तक पुष्टि के लिए इंतज़ार न करें।"]}},
}


def _healthy_management(crop: str):
    care = CROP_CARE.get(crop, {"en": ["Follow local crop recommendations and monitor regularly."], "hi": ["स्थानीय फसल सलाह अपनाएँ और नियमित निगरानी करें।"]})
    return {
        "immediate_steps": {"en": ["No disease was confidently identified on this leaf. Inspect several plants weekly and after rain.", "Keep a photo/date log if symptoms appear."],
                           "hi": ["इस पत्ती पर भरोसे के साथ कोई रोग नहीं पहचाना गया। हर सप्ताह और बारिश के बाद कई पौधों की जाँच करें।", "लक्षण दिखें तो फोटो और तारीख लिखें।"]},
        "prevention": {"en": ["Use healthy seed/planting material and locally recommended varieties.", "Base fertiliser on soil testing; use integrated pest management and avoid unnecessary pesticides."],
                       "hi": ["स्वस्थ बीज/रोपण सामग्री और स्थानीय अनुशंसित किस्में लें।", "मिट्टी जाँच के आधार पर खाद दें; समेकित कीट प्रबंधन अपनाएँ और अनावश्यक कीटनाशक न डालें।"]},
        "monitoring": {"en": ["Inspect leaves, stems and growing points regularly; a healthy-looking leaf does not rule out root, stem or field-level problems."],
                       "hi": ["पत्तियों, तनों और बढ़वार बिंदुओं की नियमित जाँच करें; स्वस्थ दिखती पत्ती जड़, तना या पूरे खेत की समस्या को खारिज नहीं करती।"]},
        "crop_care": care,
        "escalate_if": {"en": ["If symptoms spread, affect many plants, or yield declines, contact KVK/agriculture staff for field confirmation."],
                         "hi": ["लक्षण फैलें, कई पौधे प्रभावित हों या उपज घटे तो खेत में पुष्टि के लिए KVK/कृषि अधिकारी से संपर्क करें।"]},
        "chemical_safety": {"en": ["Do not apply pesticide based only on this model's result."], "hi": ["केवल इस मॉडल के नतीजे के आधार पर कीटनाशक न डालें।"]},
    }


def management_for(disease_id: str, crop: str, healthy: bool = False):
    if healthy:
        return _healthy_management(crop)
    specific = DISEASE_MANAGEMENT.get(disease_id, {})
    default = {"en": ["Take clear photos of several affected plants and ask KVK/agriculture staff to confirm before treatment."],
               "hi": ["कई प्रभावित पौधों की साफ फोटो लें और उपचार से पहले KVK/कृषि अधिकारी से पुष्टि कराएँ।"]}
    return {
        "immediate_steps": specific.get("immediate", default),
        "prevention": specific.get("prevention", default),
        "monitoring": {"en": ["Re-check the same marked plants after 2–3 days and note whether symptoms are spreading.", "Inspect more than one location; this leaf classifier cannot measure field-level disease incidence."],
                        "hi": ["2–3 दिन बाद उन्हीं चिन्हित पौधों को दोबारा देखकर फैलाव दर्ज करें।", "एक से अधिक जगह जाँचें; पत्ती का यह मॉडल पूरे खेत में रोग का स्तर नहीं मापता।"]},
        "crop_care": CROP_CARE.get(crop, default),
        "escalate_if": {"en": ["Seek prompt KVK/agriculture officer confirmation if disease spreads rapidly, many plants are affected, or the crop is near flowering/grain filling."],
                        "hi": ["रोग तेजी से फैले, कई पौधे प्रभावित हों या फसल फूल/दाना भरने की अवस्था में हो तो तुरंत KVK/कृषि अधिकारी से पुष्टि कराएँ।"]},
        "chemical_safety": {"en": ["This app does not prescribe a chemical or dose. If a pesticide is recommended by a qualified local adviser, use only a product currently registered for this crop and disease and follow its label, protective equipment and pre-harvest interval."],
                            "hi": ["यह ऐप किसी रसायन या मात्रा का नुस्खा नहीं देता। योग्य स्थानीय विशेषज्ञ दवा सुझाए तो इस फसल और रोग के लिए वर्तमान में पंजीकृत उत्पाद लें और लेबल, सुरक्षा उपकरण व कटाई-पूर्व अंतराल का पालन करें।"]},
    }

def describe(label: str):
    """Everything the app shows for a label. Unknown or invalid labels get UNSURE."""
    disease_id = match_label(label)
    if disease_id is None or disease_id == "invalid":
        return UNSURE
    info = DISEASES[disease_id]
    healthy = disease_id.endswith("_healthy")
    return {
        "id": disease_id,
        "crop": CROPS[info["crop"]],
        "name": info["name"],
        "healthy": healthy,
        "advice": info["advice"],
        "management": management_for(disease_id, info["crop"], healthy),
        "sources": [
            {"label": "ICAR crop advisories", "label_hi": "ICAR फसल सलाह", "url": "https://icar.org.in/"},
            {"label": "ICAR-CRIDA district contingency plans", "label_hi": "ICAR-CRIDA ज़िला आकस्मिक फसल योजनाएँ", "url": "https://www.icar-crida.res.in/Crop_Contingency_Plan.html"},
            {"label": "Kisan Call Centre", "label_hi": "किसान कॉल सेंटर", "url": "https://mkisan.gov.in/"},
        ],
    }
