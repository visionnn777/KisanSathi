"""Hindi display names for crops, mandi commodities, varieties, seasons and common mandi towns.

Values stored in the database stay in English (that is what the data sources use); the
frontend shows these Hindi names when Hindi is selected. Used by scripts/build_name_tables.py.
"""

# Canonical crop (see app/services/crop_catalog.py) -> Hindi
CROP_HI = {
    "rice": "चावल", "wheat": "गेहूँ", "maize": "मक्का", "barley": "जौ", "pearl millet": "बाजरा",
    "sorghum": "ज्वार", "finger millet": "रागी (मंडुआ)", "small millets": "छोटे मोटे अनाज",
    "chickpea": "चना", "pigeon pea": "अरहर (तूर)", "green gram": "मूँग", "black gram": "उड़द",
    "lentil": "मसूर", "horse gram": "कुलथी", "moth bean": "मोठ", "khesari": "खेसारी",
    "peas and beans": "मटर और सेम (दलहन)", "other kharif pulses": "अन्य खरीफ़ दलहन",
    "other rabi pulses": "अन्य रबी दलहन", "mustard": "सरसों (राई)", "soybean": "सोयाबीन",
    "groundnut": "मूँगफली", "sesame": "तिल", "linseed": "अलसी", "castor": "अरंडी",
    "sunflower": "सूरजमुखी", "safflower": "कुसुम", "niger": "रामतिल", "cotton": "कपास",
    "jute": "जूट (पटसन)", "mesta": "मेस्टा", "sunn hemp": "सनई", "sugarcane": "गन्ना",
    "potato": "आलू", "sweet potato": "शकरकंद", "tapioca": "टैपिओका (कसावा)", "onion": "प्याज़",
    "garlic": "लहसुन", "ginger": "अदरक", "turmeric": "हल्दी", "coriander": "धनिया",
    "dry chillies": "सूखी लाल मिर्च", "green chilli": "हरी मिर्च", "black pepper": "काली मिर्च",
    "cardamom": "इलायची", "arecanut": "सुपारी", "cashewnut": "काजू", "coconut": "नारियल",
    "banana": "केला", "tobacco": "तंबाकू", "guar": "ग्वार", "tomato": "टमाटर", "brinjal": "बैंगन",
    "cauliflower": "फूलगोभी", "cabbage": "पत्तागोभी",
}

# Exact names (as written by the data sources) whose Hindi differs from the plain crop name
COMMODITY_HI = {
    "Paddy": "धान", "Dhan": "धान", "Paddy(Dhan)(Common)": "धान (सामान्य)",
    "Paddy(Dhan)(Basmati)": "धान (बासमती)", "Basmati Rice": "बासमती चावल", "Rice": "चावल",
    "Dry ginger": "सोंठ", "Ginger(Dry)": "सोंठ", "Ginger(Green)": "अदरक (हरा)",
    "Kabuli Chana(Chickpeas-White)": "काबुली चना", "Bengal Gram Dal (Chana Dal)": "चना दाल",
    "Arhar Dal(Tur Dal)": "अरहर दाल", "Black Gram Dal (Urd Dal)": "उड़द दाल",
    "Green Gram Dal (Moong Dal)": "मूँग दाल", "Masur Dal": "मसूर दाल", "Moath Dal": "मोठ दाल",
    "Banana - Green": "कच्चा केला", "Coriander(Leaves)": "हरा धनिया", "Coriander seed": "धनिया (बीज)",
    "Turmeric (raw)": "कच्ची हल्दी", "Guar Seed(Cluster Beans Seed)": "ग्वार (बीज)",
    "Cluster beans": "ग्वार फली", "Groundnut pods (raw)": "मूँगफली (कच्ची फली)",
    "Gur(Jaggery)": "गुड़", "Jaggery": "गुड़", "Sugar": "चीनी", "Wheat Atta": "गेहूँ का आटा",
    "Maida Atta": "मैदा", "Soji": "सूजी", "Mustard Oil": "सरसों का तेल", "Copra": "खोपरा (सूखा नारियल)",
    "Tender Coconut": "कच्चा नारियल", "Kapas": "कपास (बिनौला सहित)", "Cotton": "कपास",
    "Cotton(lint)": "कपास (रुई)", "Apple": "सेब", "Mango": "आम", "Mango (Raw-Ripe)": "आम (कच्चा-पका)",
    "Grapes": "अंगूर", "Papaya": "पपीता", "Pomegranate": "अनार", "Orange": "संतरा", "Guava": "अमरूद",
    "Water Melon": "तरबूज", "Water Melon(Tarbuj)": "तरबूज", "Karbuja(Musk Melon)": "ख़रबूज़ा",
    "Pineapple": "अनानास", "Lemon": "नींबू", "Lime": "नींबू", "Mousambi(Sweet Lime)": "मौसमी",
    "Sapota": "चीकू", "Chikoos(Sapota)": "चीकू", "Kinnow": "किन्नू", "Litchi": "लीची",
    "Jamun(Narale Hannu)": "जामुन", "Ber(Zizyphus/Borehannu)": "बेर", "Amla(Nelli Kai)": "आंवला",
    "Custard Apple (Sharifa)": "शरीफ़ा", "Pear(Marasebu)": "नाशपाती", "Plum": "आलूबुखारा",
    "Peach": "आड़ू", "Tamarind Fruit": "इमली", "Carrot": "गाजर", "Raddish": "मूली", "Radish": "मूली",
    "Beetroot": "चुकंदर", "Bhindi(Ladies Finger)": "भिंडी", "Ladies Finger": "भिंडी",
    "Bottle gourd": "लौकी", "Bitter gourd": "करेला", "Ridgeguard(Tori)": "तोरई", "Pumpkin": "कद्दू",
    "Cucumbar(Kheera)": "खीरा", "Cucumber": "खीरा", "Capsicum": "शिमला मिर्च", "Spinach": "पालक",
    "Methi(Leaves)": "मेथी (पत्ते)", "Methi Seeds": "मेथी दाना", "Green Peas": "हरी मटर",
    "Peas Wet": "हरी मटर", "Peas(Dry)": "सूखी मटर", "Field Pea": "सूखी मटर",
    "French Beans (Frasbean)": "फ्रेंच बीन", "Cowpea(Veg)": "लोबिया (सब्ज़ी)", "Lobia": "लोबिया",
    "Colacasia": "अरबी", "Elephant Yam (Suran)": "सूरन (जिमीकंद)", "Drumstick": "सहजन",
    "Tinda": "टिंडा", "Round gourd": "टिंडा", "Little gourd (Kundru)": "कुंदरू", "Ashgourd": "पेठा",
    "Snakeguard": "चिचिंडा", "Pointed gourd (Parval)": "परवल", "Sponge gourd": "घिया तोरी",
    "Onion Green": "हरा प्याज़", "Cummin Seed(Jeera)": "जीरा", "Ajwan": "अजवाइन",
    "Niger Seed (Ramtil)": "रामतिल", "Taramira": "तारामीरा", "Toria": "तोरिया", "Rubber": "रबड़",
    "Marigold(Calcutta)": "गेंदा", "Marigold(loose)": "गेंदा", "Rose(Local)": "गुलाब",
    "Dry Fodder": "सूखा चारा", "Green Fodder": "हरा चारा", "Bhusa": "भूसा", "Fish": "मछली",
    "Mushrooms": "मशरूम", "Sweet Potato": "शकरकंद", "Leafy Vegetable": "पत्तेदार सब्ज़ी",
    "Banana flower": "केले का फूल", "Sweet Pumpkin": "मीठा कद्दू", "Chilly Capsicum": "शिमला मिर्च",
    "Other Kharif Pulses": "अन्य खरीफ़ दलहन", "Other Rabi Pulses": "अन्य रबी दलहन",
    "Peas & Beans (Pulses)": "मटर और सेम (दलहन)", "Rapeseed &Mustard": "सरसों (राई)",
}

VARIETY_HI = {
    "Other": "अन्य", "Others": "अन्य", "Local": "स्थानीय", "Desi": "देसी", "Deshi": "देसी",
    "Hybrid": "हाइब्रिड", "FAQ": "औसत गुणवत्ता (FAQ)", "Medium": "मध्यम", "Small": "छोटा",
    "Big": "बड़ा", "Large": "बड़ा", "Red": "लाल", "White": "सफ़ेद", "Yellow": "पीला",
    "Black": "काला", "Green": "हरा", "Dara": "दड़ा", "Sharbati": "शरबती", "Lokwan": "लोकवन",
    "Mill Quality": "मिल गुणवत्ता", "Common": "सामान्य", "Fine": "बारीक", "Coarse": "मोटा",
    "Super Fine": "अति बारीक", "Basmati": "बासमती", "Kabuli": "काबुली", "Bold": "मोटा दाना",
    "Dry": "सूखा", "Raw": "कच्चा", "Ripe": "पका", "Organic": "जैविक", "Average": "औसत",
    "Best": "उत्तम", "Non A/C Fine": "बारीक (नॉन A/C)", "Yellow (Black)": "पीला (काला)",
    "Desi (Whole)": "देसी (साबुत)", "Whole": "साबुत", "Split": "दली हुई", "Bhindi": "भिंडी",
    "Tomato": "टमाटर", "Onion": "प्याज़", "Potato": "आलू", "Wheat": "गेहूँ", "Mustard": "सरसों",
    "Maize": "मक्का", "1121": "1121", "Pusa Basmati 1509": "पूसा बासमती 1509",
}

SEASON_HI = {
    "Kharif": "खरीफ़", "Rabi": "रबी", "Whole Year": "पूरा वर्ष", "Summer": "गर्मी (ज़ायद)",
    "Zaid": "ज़ायद (गर्मी)", "Winter": "सर्दी", "Autumn": "शरद", "All seasons": "सभी मौसम",
    "Unknown": "अज्ञात",
}

# Mandi towns not covered by the district list. Unknown names fall back to phonetic Hindi.
MARKET_HI = {
    "Khanna": "खन्ना", "Jagraon": "जगरांव", "Samrala": "समराला", "Doraha": "दोराहा", "Raikot": "रायकोट",
    "Sahnewal": "साहनेवाल", "Machhiwara": "माछीवाड़ा", "Rajpura": "राजपुरा", "Nabha": "नाभा",
    "Samana": "समाना", "Patran": "पातड़ां", "Dhuri": "धूरी", "Sunam": "सुनाम", "Malout": "मलोट",
    "Abohar": "अबोहर", "Jalalabad": "जलालाबाद", "Zira": "ज़ीरा", "Phagwara": "फगवाड़ा",
    "Nakodar": "नकोदर", "Batala": "बटाला", "Dasuya": "दसूहा", "Mukerian": "मुकेरियां",
    "Tapa": "तपा", "Rampura Phul": "रामपुरा फूल", "Budhlada": "बुढलाडा", "Sardulgarh": "सरदूलगढ़",
    "Kotkapura": "कोटकपूरा", "Jaitu": "जैतो", "Sirhind": "सरहिंद", "Bassi Pathana": "बस्सी पठाना",
    "Morinda": "मोरिंडा", "Kharar": "खरड़", "Dera Bassi": "डेरा बस्सी", "Ahmedgarh": "अहमदगढ़",
    "Lehragaga": "लहरागागा", "Bhawanigarh": "भवानीगढ़", "Gidderbaha": "गिद्दड़बाहा",
    "Lasalgaon": "लासलगाँव", "Yeola": "येवला", "Pimpalgaon": "पिंपलगाँव", "Manmad": "मनमाड",
    "Malegaon": "मालेगाँव", "Narayangaon": "नारायणगाँव", "Baramati": "बारामती", "Junnar": "जुन्नर",
    "Shrirampur": "श्रीरामपुर", "Rahuri": "राहुरी", "Kopargaon": "कोपरगाँव", "Sangamner": "संगमनेर",
    "Lasur": "लासुर", "Vashi": "वाशी", "Kalyan": "कल्याण", "Pandharpur": "पंढरपुर",
    "Barshi": "बार्शी", "Karad": "कराड", "Phaltan": "फलटण", "Islampur": "इस्लामपुर",
    "Indore": "इंदौर", "Mhow": "महू", "Sanwer": "सांवेर", "Badnawar": "बदनावर", "Mandsaur": "मंदसौर",
    "Neemuch": "नीमच", "Jaora": "जावरा", "Shujalpur": "शुजालपुर", "Ashta": "आष्टा", "Itarsi": "इटारसी",
    "Pipariya": "पिपरिया", "Gadarwara": "गाडरवारा", "Harda": "हरदा", "Khategaon": "खातेगाँव",
    "Agra": "आगरा", "Achhnera": "अछनेरा", "Fatehabad": "फ़तेहाबाद", "Kheragarh": "खेरागढ़",
    "Bah": "बाह", "Jagner": "जगनेर", "Hathras": "हाथरस", "Khair": "खैर", "Atrauli": "अतरौली",
    "Kosikalan": "कोसीकलां", "Chhata": "छाता", "Shikohabad": "शिकोहाबाद", "Tundla": "टूंडला",
    "Jahangirabad": "जहाँगीराबाद", "Khurja": "खुर्जा", "Sikandrabad": "सिकंदराबाद", "Dadri": "दादरी",
    "Hapur": "हापुड़", "Shamli": "शामली", "Kairana": "कैराना", "Baraut": "बड़ौत", "Kasganj": "कासगंज",
    "Gola Gokarnath": "गोला गोकर्णनाथ", "Palia Kalan": "पलिया कलां", "Bahraich": "बहराइच",
    "Hubli": "हुबली", "Hubballi": "हुब्बल्ली", "Gangavathi": "गंगावती", "Sindhanur": "सिंधनूर",
    "Ranebennur": "राणेबेन्नूर", "Byadagi": "ब्याडगी", "Gokak": "गोकाक", "Chikkodi": "चिक्कोडी",
    "Bailhongal": "बैलहोंगल", "Chintamani": "चिंतामणि", "Binny Mill (F&V), Bangalore": "बिन्नी मिल (फल-सब्ज़ी), बेंगलुरु",
}

GRADE_HI = {"FAQ": "औसत गुणवत्ता (FAQ)", "Medium": "मध्यम", "Large": "बड़ा", "Small": "छोटा",
            "Local": "स्थानीय", "Non-FAQ": "औसत से कम (Non-FAQ)", "Other": "अन्य"}
