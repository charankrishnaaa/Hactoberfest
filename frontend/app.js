// Bolo - Voice-first Government Schemes Help-Desk App
// Pure Vanilla JavaScript, No Frameworks, No Build Step

(function () {
  "use strict";

  // ==================== CONFIGURATION & STATE ====================
  const API_BASE = (window.BOLO_API || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const HELPLINE_NUMBER = "1800-XXX-XXXX"; // Fallback helpline

  let currentLang = "auto";       // 'auto' | 'te' | 'hi' | 'en'
  let effectiveLang = "en";       // 'te' | 'hi' | 'en'
  let activeTab = "talk";         // 'talk' | 'schemes' | 'saved'
  let conversationHistory = [];   // Array of {role: 'user'|'bolo', text: string, kind: 'question'|'answer'}
  let allSchemes = [];
  let allCategories = [];
  let selectedCategoryFilter = "all";
  let activeSchemeDetail = null;

  // Audio & Voice State
  let audioContext = null;
  let analyserNode = null;
  let microphoneStream = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let isSpeaking = false;
  let currentUtterance = null;
  let vadInterval = null;
  let vadSilenceTimer = null;
  let vadNoSpeechTimer = null;
  let hasDetectedSpeech = false;
  let activeAbortController = null;
  let lastSentQuery = null;

  // ==================== LOCALIZATION DICTIONARY ====================
  const I18N = {
    en: {
      appName: "Bolo",
      tagline: "Village Help-Desk Volunteer",
      morningGreeting: "Good morning! I am Bolo, your village help-desk volunteer.",
      afternoonGreeting: "Good afternoon! I am Bolo, your village help-desk volunteer.",
      eveningGreeting: "Good evening! I am Bolo, your village help-desk volunteer.",
      newChat: "New Question",
      orbIdle: "Tap to talk in your language",
      orbListening: "Listening... speak now",
      orbThinking: "Thinking...",
      orbSpeaking: "Bolo is speaking... tap to stop",
      stopBolo: "Stop Bolo",
      pickTopic: "Or pick a topic to ask:",
      inputPlaceholder: "Type your question here...",
      listenAgain: "Listen again",
      callHelpline: "Call Helpline (1800-XXX-XXXX)",
      findCSC: "Find Nearest CSC / Mee Seva",
      askSomethingElse: "Ask something else",
      talkAgain: "Talk again",
      searchPlaceholder: "Search 130+ schemes (e.g. Kisan, Awas, Health)...",
      allSchemes: "All",
      benefit: "Benefit",
      eligibility: "Eligibility Criteria",
      ageIncome: "Age & Income Limits",
      documentsChecklist: "Required Documents Checklist",
      howToApply: "How to Apply",
      officialPortal: "Official Website",
      askBoloAboutThis: "Ask Bolo about this",
      listen: "Listen",
      save: "Save",
      saved: "Saved",
      savedSchemesTitle: "Saved Schemes",
      recentQuestionsTitle: "Recent Questions (Last 10)",
      clearAll: "Clear All",
      emptySaved: "No saved schemes yet. Tap the heart icon on any scheme to save it for quick offline reference.",
      emptyQuestions: "No recent questions asked yet.",
      offlineMsg: "⚠️ You are offline. Please check your internet connection.",
      wakingMsg: "⏳ Waking up server, one moment please...",
      voiceUnavailMsg: "ℹ️ Voice audio not installed for this language on your device. Text answer is displayed.",
      micDenied: "Microphone permission was denied. You can still type your questions in the box below.",
      noSpeechHeard: "I did not hear anything. Please tap the mic and try speaking again.",
      networkError: "Connection problem. Please check your network and tap Try Again.",
      tryAgain: "Try Again",
      welcomeMsg: "Namaste! I am Bolo, your village help-desk volunteer. You can talk to me directly by tapping the mic, or type your question below. How can I help you with government schemes today?",
      navTalk: "Talk",
      navSchemes: "Schemes",
      navSaved: "Saved",
      starters: [
        { cat: "Farmers", icon: "🌾", text: "What schemes are available for farmers?" },
        { cat: "Health", icon: "🏥", text: "How can I get free treatment under Ayushman Bharat?" },
        { cat: "Women & Child", icon: "👩‍👧", text: "What schemes support women and mothers?" },
        { cat: "Students", icon: "🎓", text: "What scholarships are available for students?" },
        { cat: "Pension", icon: "🧓", text: "What pension schemes are available for seniors?" },
        { cat: "Housing", icon: "🏠", text: "How can I get a house under PM Awas Yojana?" },
        { cat: "Jobs", icon: "💼", text: "What employment and skill schemes exist?" },
        { cat: "Loans", icon: "💰", text: "How can small businesses get Mudra loans?" }
      ]
    },
    hi: {
      appName: "बोलो",
      tagline: "ग्रामीण सेवा मित्र",
      morningGreeting: "शुभ प्रभात! मैं बोलो हूँ, आपका ग्रामीण सेवा मित्र।",
      afternoonGreeting: "नमस्ते! मैं बोलो हूँ, आपका ग्रामीण सेवा मित्र।",
      eveningGreeting: "शुभ संध्या! मैं बोलो हूँ, आपका ग्रामीण सेवा मित्र।",
      newChat: "नया प्रश्न",
      orbIdle: "अपनी भाषा में बात करने के लिए टैप करें",
      orbListening: "सुन रहा हूँ... अब बोलिए",
      orbThinking: "सोच रहा हूँ...",
      orbSpeaking: "बोलो बोल रहा है... रोकने के लिए टैप करें",
      stopBolo: "बोलो को रोकें",
      pickTopic: "या किसी विषय पर पूछें:",
      inputPlaceholder: "यहाँ अपना प्रश्न लिखें...",
      listenAgain: "फिर से सुनें",
      callHelpline: "हेल्पलाइन पर कॉल करें (1800-XXX-XXXX)",
      findCSC: "नज़दीकी सीएससी (CSC) खोजें",
      askSomethingElse: "कुछ और पूछें",
      talkAgain: "फिर से बोलें",
      searchPlaceholder: "130+ योजनाओं में खोजें (जैसे किसान, आवास, इलाज)...",
      allSchemes: "सभी",
      benefit: "लाभ",
      eligibility: "पात्रता (योग्यता)",
      ageIncome: "आयु और आय सीमा",
      documentsChecklist: "ज़रूरी दस्तावेज़ों की सूची",
      howToApply: "आवेदन कैसे करें",
      officialPortal: "आधिकारिक वेबसाइट",
      askBoloAboutThis: "बोलो से इसके बारे में पूछें",
      listen: "सुनें",
      save: "सेव करें",
      saved: "सेव किया गया",
      savedSchemesTitle: "सेव की गई योजनाएं",
      recentQuestionsTitle: "हाल ही में पूछे गए प्रश्न (पिछले 10)",
      clearAll: "सभी हटाएं",
      emptySaved: "अभी तक कोई योजना सेव नहीं की गई है। किसी भी योजना पर दिल के निशान को दबाकर सेव करें।",
      emptyQuestions: "अभी तक कोई प्रश्न नहीं पूछा गया है।",
      offlineMsg: "⚠️ इंटरनेट बंद है। कृपया अपना कनेक्शन जांचें।",
      wakingMsg: "⏳ सर्वर शुरू हो रहा है, एक क्षण रुकें...",
      voiceUnavailMsg: "ℹ️ आपके फ़ोन में इस भाषा की आवाज़ उपलब्ध नहीं है। नीचे लिखा हुआ उत्तर देखें।",
      micDenied: "माइक की अनुमति नहीं मिली। आप नीचे दिए गए बॉक्स में टाइप करके पूछ सकते हैं।",
      noSpeechHeard: "मुझे कोई आवाज़ नहीं सुनाई दी। कृपया माइक दबाकर दोबारा बोलें।",
      networkError: "संपर्क नहीं हो सका। कृपया नेटवर्क जांचें और दोबारा कोशिश करें।",
      tryAgain: "फिर से कोशिश करें",
      welcomeMsg: "नमस्ते! मैं बोलो हूँ, आपका ग्रामीण सेवा मित्र। आप माइक दबाकर सीधे मुझसे बात कर सकते हैं, या नीचे अपना सवाल लिख सकते हैं। सरकारी योजनाओं के बारे में मैं आपकी क्या मदद करूँ?",
      navTalk: "बात करें",
      navSchemes: "योजनाएं",
      navSaved: "सेव किए गए",
      starters: [
        { cat: "Farmers", icon: "🌾", text: "किसानों के लिए कौन सी प्रमुख सरकारी योजनाएं हैं?" },
        { cat: "Health", icon: "🏥", text: "आयुष्मान भारत कार्ड से मुफ्त इलाज कैसे मिलता है?" },
        { cat: "Women & Child", icon: "👩‍👧", text: "महिलाओं और माताओं के लिए कौन सी योजनाएं हैं?" },
        { cat: "Students", icon: "🎓", text: "छात्रों के लिए छात्रवृत्ति (Scholarship) योजनाएं क्या हैं?" },
        { cat: "Pension", icon: "🧓", text: "बुजुर्गों के लिए कौन सी पेंशन योजना है?" },
        { cat: "Housing", icon: "🏠", text: "पीएम आवास योजना से पक्का मकान कैसे मिल सकता है?" },
        { cat: "Jobs", icon: "💼", text: "रोजगार और कौशल विकास की योजनाएं क्या हैं?" },
        { cat: "Loans", icon: "💰", text: "छोटे व्यापार के लिए मुद्रा लोन कैसे मिलता है?" }
      ]
    },
    te: {
      appName: "బోలో",
      tagline: "గ్రామ సహాయక మిత్రుడు",
      morningGreeting: "శుభోదయం! నేను బోలోను, మీ గ్రామ సహాయకుడిని.",
      afternoonGreeting: "నమస్కారం! నేను బోలోను, మీ గ్రామ సహాయకుడిని.",
      eveningGreeting: "శుభ సాయంత్రం! నేను బోలోను, మీ గ్రామ సహాయకుడిని.",
      newChat: "కొత్త ప్రశ్న",
      orbIdle: "మాట్లాడటానికి తాకండి",
      orbListening: "వింటున్నాను... మాట్లాడండి",
      orbThinking: "ఆలోచిస్తున్నాను...",
      orbSpeaking: "బోలో మాట్లాడుతున్నారు... ఆపడానికి తాకండి",
      stopBolo: "ఆపండి",
      pickTopic: "లేదా ఒక పథకం గురించి అడగండి:",
      inputPlaceholder: "ఇక్కడ టైప్ చేయండి...",
      listenAgain: "మళ్ళీ వినండి",
      callHelpline: "హెల్ప్‌లైన్‌కు కాల్ చేయండి (1800-XXX-XXXX)",
      findCSC: "మీ సేవ / CSC కేంద్రాన్ని కనుగొనండి",
      askSomethingElse: "మరొకటి అడగండి",
      talkAgain: "మళ్ళీ మాట్లాడండి",
      searchPlaceholder: "130+ పథకాల్లో వెతకండి (ఉదా: కిసాన్, ఆవాస్, ఆరోగ్యం)...",
      allSchemes: "అన్నీ",
      benefit: "లభించే ప్రయోజనం",
      eligibility: "అర్హతలు",
      ageIncome: "వయస్సు & ఆదాయ పరిమితులు",
      documentsChecklist: "కావలసిన పత్రాల జాబితా",
      howToApply: "దరఖాస్తు చేసుకునే విధానం",
      officialPortal: "అధికారిక వెబ్‌సైట్",
      askBoloAboutThis: "ఈ పథకం గురించి బోలోను అడగండి",
      listen: "వినండి",
      save: "సేవ్ చేయండి",
      saved: "సేవ్ చేయబడింది",
      savedSchemesTitle: "సేవ్ చేసిన పథకాలు",
      recentQuestionsTitle: "ఇటీవలి ప్రశ్నలు (చివరి 10)",
      clearAll: "అన్నీ తొలగించండి",
      emptySaved: "ఇంకా ఏ పథకాలు సేవ్ చేయలేదు. ఏదైనా పథకంపై గుండె గుర్తును నొక్కి సేవ్ చేసుకోండి.",
      emptyQuestions: "ఇంకా ప్రశ్నలు ఏమీ అడగలేదు.",
      offlineMsg: "⚠️ ఇంటర్నెట్ కనెక్షన్ లేదు. దయచేసి నెట్‌వర్క్ తనిఖీ చేయండి.",
      wakingMsg: "⏳ సర్వర్ కనెక్ట్ అవుతోంది, ఒక్క నిమిషం వేచి ఉండండి...",
      voiceUnavailMsg: "ℹ️ మీ ఫోన్‌లో ఈ భాషా వాయిస్ లేదు. సమాధానం కింద వచన రూపంలో కనిపిస్తుంది.",
      micDenied: "మైక్రోఫోన్ అనుమతి రాలేదు. కింద ఉన్న బాక్స్‌లో టైప్ చేసి అడగవచ్చు.",
      noSpeechHeard: "నాకు మాటలు వినిపించలేదు. దయచేసి మైక్ తాకి మళ్ళీ మాట్లాడండి.",
      networkError: "కనెక్ట్ కాలేకపోయాము. దయచేసి నెట్‌వర్క్ చూసి మళ్ళీ ప్రయత్నించండి.",
      tryAgain: "మళ్ళీ ప్రయత్నించండి",
      welcomeMsg: "నమస్కారం! నేను బోలోను, మీ గ్రామ సహాయకుడిని. మీరు మైక్ తాకి నాతో నేరుగా మాట్లాడవచ్చు, లేదా కింద మీ ప్రశ్నను టైప్ చేయవచ్చు. ప్రభుత్వ పథకాల గురించి నేను మీకు ఎలా సహాయపడగలను?",
      navTalk: "మాట్లాడండి",
      navSchemes: "పథకాలు",
      navSaved: "సేవ్ చేసినవి",
      starters: [
        { cat: "Farmers", icon: "🌾", text: "రైతులకు ఉన్న ముఖ్యమైన ప్రభుత్వ పథకాలు ఏమిటి?" },
        { cat: "Health", icon: "🏥", text: "ఆయుష్మాన్ భారత్ ద్వారా ఉచిత చికిత్స ఎలా పొందాలి?" },
        { cat: "Women & Child", icon: "👩‍👧", text: "మహిళలకు మరియు గర్భిణులకు ఇచ్చే పథకాలు ఏమిటి?" },
        { cat: "Students", icon: "🎓", text: "విద్యార్థులకు స్కాలర్‌షిప్ పథకాలు ఏమిటి?" },
        { cat: "Pension", icon: "🧓", text: "వృద్ధులకు ఇచ్చే పింఛన్ పథకం వివరాలు ఏమిటి?" },
        { cat: "Housing", icon: "🏠", text: "పీఎం ఆవాస్ యోజన ఇళ్ల పథకం వివరాలు ఏమిటి?" },
        { cat: "Jobs", icon: "💼", text: "యువతకు ఉపాధి మరియు నైపుణ్య శిక్షణ పథకాలు ఏమిటి?" },
        { cat: "Loans", icon: "💰", text: "చిన్న వ్యాపారాలకు ముద్ర రుణాలు ఎలా లభిస్తాయి?" }
      ]
    }
  };

  function getT() {
    return I18N[effectiveLang] || I18N.en;
  }

  // ==================== DOM ELEMENTS ====================
  const dom = {
    ariaStatus: document.getElementById("aria-status"),
    headerGreeting: document.getElementById("header-greeting"),
    btnNewChat: document.getElementById("btn-new-chat"),
    lblNewChat: document.getElementById("lbl-new-chat"),
    langBtns: document.querySelectorAll(".lang-btn"),
    
    // Banners
    bannerOffline: document.getElementById("banner-offline"),
    bannerWaking: document.getElementById("banner-waking"),
    bannerVoiceUnavail: document.getElementById("banner-voice-unavail"),

    // Screens
    screenTalk: document.getElementById("screen-talk"),
    screenSchemes: document.getElementById("screen-schemes"),
    screenSaved: document.getElementById("screen-saved"),

    // Nav Tabs
    tabBtnTalk: document.getElementById("tab-btn-talk"),
    tabBtnSchemes: document.getElementById("tab-btn-schemes"),
    tabBtnSaved: document.getElementById("tab-btn-saved"),
    navLblTalk: document.getElementById("nav-lbl-talk"),
    navLblSchemes: document.getElementById("nav-lbl-schemes"),
    navLblSaved: document.getElementById("nav-lbl-saved"),

    // Orb & Talk
    orbWrapper: document.getElementById("orb-wrapper"),
    orbStatus: document.getElementById("orb-status"),
    btnStopSpeaking: document.getElementById("btn-stop-speaking"),
    lblStopVoice: document.getElementById("lbl-stop-voice"),
    starterTilesContainer: document.getElementById("starter-tiles-container"),
    lblStarterTopics: document.getElementById("lbl-starter-topics"),
    chatMessages: document.getElementById("chat-messages"),
    welcomeBubbleMsg: document.getElementById("welcome-bubble-msg"),
    chatTextInput: document.getElementById("chat-text-input"),
    btnSendText: document.getElementById("btn-send-text"),

    // Schemes Screen
    schemesSearchInput: document.getElementById("schemes-search-input"),
    categoriesFilterScroll: document.getElementById("categories-filter-scroll"),
    schemesCardsList: document.getElementById("schemes-cards-list"),

    // Saved Screen
    savedSchemesContainer: document.getElementById("saved-schemes-container"),
    recentQuestionsContainer: document.getElementById("recent-questions-container"),
    btnClearQuestions: document.getElementById("btn-clear-questions"),
    lblSavedSchemesTitle: document.getElementById("lbl-saved-schemes-title"),
    lblRecentQuestionsTitle: document.getElementById("lbl-recent-questions-title"),
    lblEmptySaved: document.getElementById("lbl-empty-saved"),
    lblEmptyQuestions: document.getElementById("lbl-empty-questions"),

    // Bottom Sheet
    bottomSheetBackdrop: document.getElementById("bottom-sheet-backdrop"),
    bottomSheetContent: document.getElementById("bottom-sheet-content"),
    btnCloseSheet: document.getElementById("btn-close-sheet"),
    sheetCatBadge: document.getElementById("sheet-cat-badge"),
    sheetSchemeTitle: document.getElementById("sheet-scheme-title"),
    sheetVerifiedDate: document.getElementById("sheet-verified-date"),
    sheetBenefitBox: document.getElementById("sheet-benefit-box"),
    sheetDescContent: document.getElementById("sheet-desc-content"),
    sheetEligibilityContent: document.getElementById("sheet-eligibility-content"),
    sheetAgeContent: document.getElementById("sheet-age-content"),
    sheetIncomeContent: document.getElementById("sheet-income-content"),
    sheetDocsChecklist: document.getElementById("sheet-docs-checklist"),
    sheetApplyContent: document.getElementById("sheet-apply-content"),
    sheetOfficialUrl: document.getElementById("sheet-official-url"),
    sheetBtnAsk: document.getElementById("sheet-btn-ask"),
    sheetBtnListen: document.getElementById("sheet-btn-listen"),
    sheetBtnSave: document.getElementById("sheet-btn-save"),
    sheetBtnWhatsapp: document.getElementById("sheet-btn-whatsapp"),
    lblSheetAsk: document.getElementById("lbl-sheet-ask"),
    lblSheetListen: document.getElementById("lbl-sheet-listen"),
    lblSheetSave: document.getElementById("lbl-sheet-save")
  };

  // ==================== INITIALIZATION ====================
  function init() {
    updateEffectiveLanguage();
    updateUIStrings();
    setupEventListeners();
    fetchCategories();
    fetchSchemes();
    renderSavedScreen();
    registerServiceWorker();
    checkNetworkStatus();

    // Initial welcome voice trigger setup
    document.querySelectorAll(".welcome-listen-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        bargeIn();
        speakText(dom.welcomeBubbleMsg.textContent, effectiveLang);
      });
    });
  }

  // Determine greeting based on current time
  function getTimeGreeting() {
    const hour = new Date().getHours();
    const t = getT();
    if (hour < 12) return t.morningGreeting;
    if (hour < 17) return t.afternoonGreeting;
    return t.eveningGreeting;
  }

  function updateEffectiveLanguage() {
    if (currentLang === "auto") {
      // Keep effectiveLang as previously detected or default to Telugu or English
      // If user hasn't set anything, start with English/Telugu friendly
    } else {
      effectiveLang = currentLang;
    }
  }

  function updateUIStrings() {
    const t = getT();
    dom.headerGreeting.textContent = getTimeGreeting();
    dom.lblNewChat.textContent = t.newChat;
    dom.lblStopVoice.textContent = t.stopBolo;
    dom.lblStarterTopics.textContent = t.pickTopic;
    dom.chatTextInput.placeholder = t.inputPlaceholder;
    dom.schemesSearchInput.placeholder = t.searchPlaceholder;
    dom.lblSavedSchemesTitle.textContent = t.savedSchemesTitle;
    dom.lblRecentQuestionsTitle.textContent = t.recentQuestionsTitle;
    dom.btnClearQuestions.textContent = t.clearAll;
    dom.lblEmptySaved.textContent = t.emptySaved;
    dom.lblEmptyQuestions.textContent = t.emptyQuestions;
    dom.navLblTalk.textContent = t.navTalk;
    dom.navLblSchemes.textContent = t.navSchemes;
    dom.navLblSaved.textContent = t.navSaved;
    dom.welcomeBubbleMsg.textContent = t.welcomeMsg;

    if (dom.orbWrapper.classList.contains("state-idle")) {
      dom.orbStatus.textContent = t.orbIdle;
    }

    renderStarterTiles();
  }

  function setLanguage(lang) {
    currentLang = lang;
    dom.langBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.lang === lang);
    });

    if (lang !== "auto") {
      effectiveLang = lang;
    }
    updateUIStrings();
    announceAria(`Language set to ${lang}`);
  }

  function announceAria(text) {
    if (dom.ariaStatus) {
      dom.ariaStatus.textContent = text;
    }
  }

  // ==================== NAVIGATION TABS ====================
  function switchTab(tab) {
    bargeIn();
    activeTab = tab;

    dom.tabBtnTalk.classList.toggle("active", tab === "talk");
    dom.tabBtnSchemes.classList.toggle("active", tab === "schemes");
    dom.tabBtnSaved.classList.toggle("active", tab === "saved");

    dom.screenTalk.classList.toggle("active", tab === "talk");
    dom.screenSchemes.classList.toggle("active", tab === "schemes");
    dom.screenSaved.classList.toggle("active", tab === "saved");

    if (tab === "saved") {
      renderSavedScreen();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ==================== STARTER TILES ====================
  function renderStarterTiles() {
    const t = getT();
    dom.starterTilesContainer.replaceChildren();

    t.starters.forEach((item) => {
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "starter-tile";
      
      const iconSpan = document.createElement("span");
      iconSpan.className = "tile-icon";
      iconSpan.textContent = item.icon;

      const textSpan = document.createElement("span");
      textSpan.textContent = item.cat;

      tile.appendChild(iconSpan);
      tile.appendChild(textSpan);

      tile.addEventListener("click", () => {
        bargeIn();
        resetConversation();
        handleUserQuestion(item.text, effectiveLang);
      });

      dom.starterTilesContainer.appendChild(tile);
    });
  }

  // ==================== CHAT & CONVERSATION ====================
  function resetConversation() {
    conversationHistory = [];
    // Keep only the first welcome bubble
    const rows = dom.chatMessages.querySelectorAll(".chat-row");
    for (let i = 1; i < rows.length; i++) {
      rows[i].remove();
    }
    announceAria("Started fresh conversation.");
  }

  function appendChatBubble(role, text, meta = {}) {
    const row = document.createElement("div");
    row.className = `chat-row ${role}`;

    if (role === "bolo") {
      const avatarDiv = document.createElement("div");
      avatarDiv.className = "bubble-avatar";
      avatarDiv.setAttribute("aria-hidden", "true");
      avatarDiv.innerHTML = `
        <svg viewBox="0 0 512 512" width="100%" height="100%">
          <circle cx="256" cy="256" r="240" fill="#2f4a9e"/>
          <circle cx="256" cy="245" r="70" fill="#fbd5b5"/>
          <path d="M 186 215 C 180 160, 215 130, 256 130 C 297 130, 332 160, 326 215 Z" fill="#f08a24"/>
          <circle cx="234" cy="240" r="6" fill="#3c2415"/>
          <circle cx="278" cy="240" r="6" fill="#3c2415"/>
          <path d="M 234 270 Q 256 295 278 270" fill="none" stroke="#683416" stroke-width="5" stroke-linecap="round"/>
        </svg>
      `;
      row.appendChild(avatarDiv);
    }

    const bubble = document.createElement("div");
    bubble.className = `bubble ${role === "user" ? "user-bubble" : "bolo-bubble"}`;
    if (meta.type === "unknown") {
      bubble.classList.add("unknown-bubble");
    }

    const textDiv = document.createElement("div");
    textDiv.className = "bubble-text";
    textDiv.textContent = text;
    bubble.appendChild(textDiv);

    // Bolo Actions
    if (role === "bolo") {
      const footer = document.createElement("div");
      footer.className = "bubble-footer";

      const toolsRow = document.createElement("div");
      toolsRow.className = "bubble-tools-row";

      // Listen again button
      const listenBtn = document.createElement("button");
      listenBtn.type = "button";
      listenBtn.className = "listen-again-btn";
      listenBtn.textContent = `🔊 ${getT().listenAgain}`;
      listenBtn.addEventListener("click", () => {
        bargeIn();
        speakText(text, meta.lang || effectiveLang);
      });
      toolsRow.appendChild(listenBtn);

      // Official Scheme Sources
      if (meta.sources && meta.sources.length > 0) {
        const sourcesDiv = document.createElement("div");
        sourcesDiv.className = "sources-container";
        meta.sources.forEach((s) => {
          if (s.url) {
            const link = document.createElement("a");
            link.className = "source-chip";
            link.href = s.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = `🔗 ${s.name || "Official Portal"}`;
            sourcesDiv.appendChild(link);
          }
        });
        toolsRow.appendChild(sourcesDiv);
      }

      footer.appendChild(toolsRow);

      // Follow-up Question Options
      if (meta.type === "question" && Array.isArray(meta.options) && meta.options.length > 0) {
        const optsContainer = document.createElement("div");
        optsContainer.className = "options-container";
        meta.options.forEach((optText) => {
          const optBtn = document.createElement("button");
          optBtn.type = "button";
          optBtn.className = "option-btn";
          optBtn.textContent = optText;
          optBtn.addEventListener("click", () => {
            bargeIn();
            handleUserQuestion(optText, effectiveLang);
          });
          optsContainer.appendChild(optBtn);
        });
        footer.appendChild(optsContainer);
      }

      // Unknown response actions
      if (meta.type === "unknown") {
        const helplineDiv = document.createElement("div");
        helplineDiv.className = "helpline-actions";

        const callBtn = document.createElement("a");
        callBtn.className = "helpline-btn call";
        callBtn.href = `tel:${HELPLINE_NUMBER}`;
        callBtn.textContent = `📞 ${getT().callHelpline}`;
        helplineDiv.appendChild(callBtn);

        const cscBtn = document.createElement("a");
        cscBtn.className = "helpline-btn locator";
        cscBtn.href = "https://locator.csccloud.in/";
        cscBtn.target = "_blank";
        cscBtn.rel = "noopener noreferrer";
        cscBtn.textContent = `📍 ${getT().findCSC}`;
        helplineDiv.appendChild(cscBtn);

        footer.appendChild(helplineDiv);
      }

      // Retry button for errors
      if (meta.isError && meta.retryPayload) {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.className = "option-btn";
        retryBtn.style.background = "var(--primary)";
        retryBtn.textContent = `🔄 ${getT().tryAgain}`;
        retryBtn.addEventListener("click", () => {
          bargeIn();
          handleUserQuestion(meta.retryPayload.question, meta.retryPayload.lang);
        });
        footer.appendChild(retryBtn);
      }

      bubble.appendChild(footer);
    }

    row.appendChild(bubble);
    dom.chatMessages.appendChild(row);

    // Scroll chat into view
    row.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Save to recent questions list
  function saveRecentQuestion(q) {
    if (!q || !q.trim()) return;
    try {
      let list = JSON.parse(localStorage.getItem("bolo_recent_questions") || "[]");
      list = list.filter((item) => item !== q);
      list.unshift(q);
      if (list.length > 10) list = list.slice(0, 10);
      localStorage.setItem("bolo_recent_questions", JSON.stringify(list));
    } catch (e) {
      console.warn("Could not save question to localStorage:", e);
    }
  }

  // ==================== ASYNC API CALLS ====================
  async function handleUserQuestion(questionText, reqLang = "auto") {
    if (!questionText || !questionText.trim()) return;

    bargeIn();
    const cleanText = questionText.trim();
    lastSentQuery = cleanText;
    saveRecentQuestion(cleanText);

    // Render user speech bubble
    appendChatBubble("user", cleanText);

    // Update conversation history
    conversationHistory.push({
      role: "user",
      text: cleanText,
      kind: "question"
    });

    // Set UI to thinking
    setOrbState("thinking");
    showWakingBannerTimer();

    activeAbortController = new AbortController();
    const timeoutId = setTimeout(() => {
      if (activeAbortController) {
        activeAbortController.abort();
      }
    }, 25000);

    try {
      const resp = await fetch(`${API_BASE}/ask-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: cleanText,
          lang: currentLang === "auto" ? "auto" : reqLang,
          history: conversationHistory.slice(-6)
        }),
        signal: activeAbortController.signal
      });

      clearTimeout(timeoutId);
      hideWakingBanner();

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const data = await resp.json();
      handleBoloResponse(data);
    } catch (err) {
      clearTimeout(timeoutId);
      hideWakingBanner();
      setOrbState("idle");

      if (err.name === "AbortError") {
        console.log("Request was aborted (barge-in or timeout).");
        return;
      }

      console.error("Error communicating with Bolo backend:", err);
      appendChatBubble("bolo", getT().networkError, {
        type: "unknown",
        isError: true,
        retryPayload: { question: cleanText, lang: reqLang }
      });
      speakText(getT().networkError, effectiveLang);
    }
  }

  async function handleVoiceAudioUpload(audioBlob) {
    bargeIn();
    setOrbState("thinking");
    showWakingBannerTimer();

    activeAbortController = new AbortController();
    const timeoutId = setTimeout(() => {
      if (activeAbortController) {
        activeAbortController.abort();
      }
    }, 25000);

    try {
      const formData = new FormData();
      const ext = audioBlob.type.includes("mp4") ? "mp4" : "webm";
      formData.append("audio", audioBlob, `voice_recording.${ext}`);
      formData.append("lang", currentLang);
      formData.append("history", JSON.stringify(conversationHistory.slice(-6)));

      const resp = await fetch(`${API_BASE}/ask-voice`, {
        method: "POST",
        body: formData,
        signal: activeAbortController.signal
      });

      clearTimeout(timeoutId);
      hideWakingBanner();

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const data = await resp.json();
      
      // If voice was transcribed, show user bubble with what was heard
      if (data.transcript && data.transcript.trim()) {
        appendChatBubble("user", data.transcript);
        saveRecentQuestion(data.transcript);
        conversationHistory.push({
          role: "user",
          text: data.transcript,
          kind: "question"
        });
      }

      handleBoloResponse(data);
    } catch (err) {
      clearTimeout(timeoutId);
      hideWakingBanner();
      setOrbState("idle");

      if (err.name === "AbortError") {
        console.log("Voice request was aborted.");
        return;
      }

      console.error("Voice upload error:", err);
      appendChatBubble("bolo", getT().networkError, {
        type: "unknown",
        isError: true
      });
      speakText(getT().networkError, effectiveLang);
    }
  }

  function handleBoloResponse(data) {
    // If backend detected language and we are in auto mode, update effective language
    if (data.lang && ["en", "hi", "te"].includes(data.lang)) {
      effectiveLang = data.lang;
      if (currentLang === "auto") {
        updateUIStrings();
      }
    }

    // Append Bolo chat bubble
    appendChatBubble("bolo", data.text, {
      type: data.type,
      options: data.options,
      sources: data.sources,
      lang: effectiveLang
    });

    // Save to conversation history
    conversationHistory.push({
      role: "bolo",
      text: data.text,
      kind: data.type === "question" ? "question" : "answer"
    });

    // Speak response
    speakText(data.text, effectiveLang, () => {
      // Callback after speaking completes:
      // CONVERSATION MODE: If Bolo asked a question, auto-start listening!
      if (data.type === "question") {
        setTimeout(() => {
          if (!isSpeaking && activeTab === "talk") {
            startVoiceRecording();
          }
        }, 350);
      }
    });
  }

  // Waking server banner (triggers if server takes > 4s)
  let wakingTimer = null;
  function showWakingBannerTimer() {
    clearTimeout(wakingTimer);
    wakingTimer = setTimeout(() => {
      dom.bannerWaking.classList.add("active");
    }, 4000);
  }

  function hideWakingBanner() {
    clearTimeout(wakingTimer);
    dom.bannerWaking.classList.remove("active");
  }

  // ==================== VOICE / AUDIO & VAD ENGINE ====================
  function setOrbState(state) {
    dom.orbWrapper.className = `orb-container state-${state}`;
    const t = getT();
    if (state === "idle") {
      dom.orbStatus.textContent = t.orbIdle;
    } else if (state === "listening") {
      dom.orbStatus.textContent = t.orbListening;
    } else if (state === "thinking") {
      dom.orbStatus.textContent = t.orbThinking;
    } else if (state === "speaking") {
      dom.orbStatus.textContent = t.orbSpeaking;
    }
  }

  async function startVoiceRecording() {
    bargeIn();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      microphoneStream = stream;

      // Initialize Web Audio Context for live mic visualization & VAD
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!audioContext) {
        audioContext = new AudioCtx();
      }
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }

      const sourceNode = audioContext.createMediaStreamSource(stream);
      analyserNode = audioContext.createAnalyser();
      analyserNode.fftSize = 256;
      sourceNode.connect(analyserNode);

      // Pick supported mimeType (webm or mp4 for Safari)
      let mimeType = "audio/webm;codecs=opus";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : (MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "");
      }

      mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunks = [];
      hasDetectedSpeech = false;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        cleanupAudioNodes();
        if (hasDetectedSpeech && audioChunks.length > 0) {
          const recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
          handleVoiceAudioUpload(recordedBlob);
        } else {
          setOrbState("idle");
          announceAria(getT().noSpeechHeard);
        }
      };

      mediaRecorder.start(200);
      isRecording = true;
      setOrbState("listening");

      // VAD Monitoring Loop
      setupVAD();

    } catch (err) {
      console.error("Microphone access error:", err);
      setOrbState("idle");
      alert(getT().micDenied);
    }
  }

  function stopVoiceRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
    isRecording = false;
  }

  function cleanupAudioNodes() {
    clearInterval(vadInterval);
    clearTimeout(vadSilenceTimer);
    clearTimeout(vadNoSpeechTimer);

    if (microphoneStream) {
      microphoneStream.getTracks().forEach((track) => track.stop());
      microphoneStream = null;
    }
  }

  function setupVAD() {
    const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
    let silenceStart = null;
    const speechThreshold = 22; // RMS noise gate
    const silenceDuration = 1600; // ms of silence before auto-stop

    // 8s absolute silence timeout: if user didn't speak at all
    vadNoSpeechTimer = setTimeout(() => {
      if (!hasDetectedSpeech && isRecording) {
        console.log("No speech detected after 8s.");
        stopVoiceRecording();
        alert(getT().noSpeechHeard);
      }
    }, 8000);

    // 25s max recording safety limit
    setTimeout(() => {
      if (isRecording) {
        console.log("Max duration 25s reached. Stopping recording.");
        stopVoiceRecording();
      }
    }, 25000);

    vadInterval = setInterval(() => {
      if (!analyserNode || !isRecording) return;
      analyserNode.getByteFrequencyData(dataArray);

      // Calculate simple average amplitude
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;

      // Live visual ripple scale reacting to voice level
      const ripple1 = document.querySelector(".orb-ripple-1");
      if (ripple1) {
        const scale = 1.0 + Math.min(average / 45, 0.6);
        ripple1.style.transform = `scale(${scale})`;
      }

      if (average > speechThreshold) {
        hasDetectedSpeech = true;
        silenceStart = null;
      } else {
        if (hasDetectedSpeech) {
          if (!silenceStart) {
            silenceStart = Date.now();
          } else if (Date.now() - silenceStart > silenceDuration) {
            console.log("VAD auto-stop triggered after user finished speaking.");
            stopVoiceRecording();
          }
        }
      }
    }, 60);
  }

  // ==================== SPEECH SYNTHESIS (TTS) ====================
  function speakText(textToSpeak, langCode, onCompleteCallback) {
    if (!window.speechSynthesis) {
      if (onCompleteCallback) onCompleteCallback();
      return;
    }

    // Cancel any active speech
    window.speechSynthesis.cancel();

    // Clean markdown/symbols from speech
    const cleanSpoken = textToSpeak.replace(/[*#_`]/g, "").trim();
    if (!cleanSpoken) {
      if (onCompleteCallback) onCompleteCallback();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(cleanSpoken);
    currentUtterance = utterance;

    // Resolve voice language
    const langTag = langCode === "te" ? "te-IN" : (langCode === "hi" ? "hi-IN" : "en-IN");
    utterance.lang = langTag;
    utterance.rate = 0.95; // Slightly slower, clear village volunteer cadence
    utterance.pitch = 1.0;

    // Find best installed voice
    const voices = window.speechSynthesis.getVoices();
    let bestVoice = voices.find((v) => v.lang.replace("_", "-") === langTag);
    if (!bestVoice) {
      bestVoice = voices.find((v) => v.lang.startsWith(langCode));
    }
    if (bestVoice) {
      utterance.voice = bestVoice;
    } else {
      // Check if neither voice nor lang matches
      if (langCode === "te" && !voices.some((v) => v.lang.includes("te"))) {
        dom.bannerVoiceUnavail.classList.add("active");
        setTimeout(() => dom.bannerVoiceUnavail.classList.remove("active"), 5000);
      }
    }

    utterance.onstart = () => {
      isSpeaking = true;
      setOrbState("speaking");
    };

    utterance.onend = () => {
      isSpeaking = false;
      setOrbState("idle");
      if (onCompleteCallback) onCompleteCallback();
    };

    utterance.onerror = (e) => {
      console.warn("Speech synthesis error:", e);
      isSpeaking = false;
      setOrbState("idle");
      if (onCompleteCallback) onCompleteCallback();
    };

    window.speechSynthesis.speak(utterance);
  }

  // BARGE-IN: Instantly cancel TTS and abort active network requests
  function bargeIn() {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    isSpeaking = false;

    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }

    if (isRecording) {
      stopVoiceRecording();
    }

    hideWakingBanner();
    setOrbState("idle");
  }

  // ==================== SCHEMES BROWSER & BOTTOM SHEET ====================
  async function fetchCategories() {
    try {
      const resp = await fetch(`${API_BASE}/categories`);
      if (resp.ok) {
        allCategories = await resp.json();
        renderCategoryFilterChips();
      }
    } catch (e) {
      console.warn("Could not fetch categories:", e);
    }
  }

  async function fetchSchemes(category = "", query = "") {
    try {
      let url = `${API_BASE}/schemes`;
      const params = new URLSearchParams();
      if (category && category !== "all") params.append("category", category);
      if (query && query.trim()) params.append("q", query.trim());
      if ([...params].length > 0) url += `?${params.toString()}`;

      const resp = await fetch(url);
      if (resp.ok) {
        allSchemes = await resp.json();
        renderSchemesList();
      }
    } catch (e) {
      console.error("Could not fetch schemes:", e);
    }
  }

  function renderCategoryFilterChips() {
    dom.categoriesFilterScroll.replaceChildren();

    // "All" chip
    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = `cat-filter-btn ${selectedCategoryFilter === "all" ? "active" : ""}`;
    allBtn.textContent = `${getT().allSchemes} (130)`;
    allBtn.addEventListener("click", () => {
      selectedCategoryFilter = "all";
      document.querySelectorAll(".cat-filter-btn").forEach((b) => b.classList.remove("active"));
      allBtn.classList.add("active");
      fetchSchemes("", dom.schemesSearchInput.value);
    });
    dom.categoriesFilterScroll.appendChild(allBtn);

    allCategories.forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `cat-filter-btn ${selectedCategoryFilter === cat.name ? "active" : ""}`;
      btn.textContent = `${cat.name} (${cat.count})`;
      btn.addEventListener("click", () => {
        selectedCategoryFilter = cat.name;
        document.querySelectorAll(".cat-filter-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        fetchSchemes(cat.name, dom.schemesSearchInput.value);
      });
      dom.categoriesFilterScroll.appendChild(btn);
    });
  }

  function getCategoryColorClass(catName) {
    if (!catName) return "other";
    const low = catName.toLowerCase();
    if (low.includes("farmer")) return "farmers";
    if (low.includes("health")) return "health";
    if (low.includes("women") || low.includes("child")) return "women";
    if (low.includes("student")) return "students";
    if (low.includes("pension") || low.includes("senior")) return "pension";
    if (low.includes("housing")) return "housing";
    if (low.includes("job") || low.includes("skill")) return "jobs";
    if (low.includes("loan") || low.includes("business")) return "loans";
    if (low.includes("insurance")) return "insurance";
    if (low.includes("disability")) return "disability";
    if (low.includes("village")) return "village";
    return "other";
  }

  function renderSchemesList() {
    dom.schemesCardsList.replaceChildren();

    if (allSchemes.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No schemes found matching your search.";
      dom.schemesCardsList.appendChild(empty);
      return;
    }

    allSchemes.forEach((s) => {
      const card = document.createElement("div");
      card.className = "scheme-card";
      card.tabIndex = 0;
      card.role = "button";
      card.setAttribute("aria-label", `View details for ${s.name}`);

      const topRow = document.createElement("div");
      topRow.className = "card-top";

      const catTag = document.createElement("span");
      catTag.className = `cat-tag ${getCategoryColorClass(s.category)}`;
      catTag.textContent = s.category;
      topRow.appendChild(catTag);

      card.appendChild(topRow);

      const title = document.createElement("div");
      title.className = "card-title";
      title.textContent = s.name;
      card.appendChild(title);

      const desc = document.createElement("div");
      desc.className = "card-desc";
      desc.textContent = s.short;
      card.appendChild(desc);

      if (s.benefit) {
        const benefitChip = document.createElement("div");
        benefitChip.className = "benefit-chip";
        benefitChip.textContent = `💰 ${s.benefit}`;
        card.appendChild(benefitChip);
      }

      card.addEventListener("click", () => openSchemeDetails(s.id));
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openSchemeDetails(s.id);
        }
      });

      dom.schemesCardsList.appendChild(card);
    });
  }

  async function openSchemeDetails(schemeId) {
    bargeIn();
    try {
      const resp = await fetch(`${API_BASE}/schemes/${schemeId}`);
      if (!resp.ok) throw new Error("Could not load scheme");
      const s = await resp.json();
      activeSchemeDetail = s;

      // Populate bottom sheet fields safely
      dom.sheetCatBadge.className = `cat-tag ${getCategoryColorClass(s.category)}`;
      dom.sheetCatBadge.textContent = s.category;
      dom.sheetSchemeTitle.textContent = s.scheme_name;
      dom.sheetVerifiedDate.textContent = s.source_and_verification_date || "Verified 2026";
      dom.sheetBenefitBox.textContent = `💰 Benefit: ${s.benefits_money || "Financial / In-kind Assistance"}`;
      dom.sheetDescContent.textContent = s.scheme_description;
      dom.sheetEligibilityContent.textContent = s.eligibility;
      dom.sheetAgeContent.textContent = s.age_limit || "No specific age limit";
      dom.sheetIncomeContent.textContent = s.income_limit || "No specific income limit";
      dom.sheetApplyContent.textContent = s.application_process;
      dom.sheetOfficialUrl.href = s.application_url || "#";

      // Render interactive documents checklist
      renderDocumentsChecklist(s.id, s.documents || []);

      // Check bookmark status
      updateSaveButtonUI(s.id);

      // Setup actions
      dom.sheetBtnAsk.onclick = () => {
        closeBottomSheet();
        switchTab("talk");
        handleUserQuestion(`Can you explain ${s.scheme_name} and am I eligible?`, effectiveLang);
      };

      dom.sheetBtnListen.onclick = () => {
        bargeIn();
        const speechSummary = `${s.scheme_name}. ${s.scheme_description}. Benefit: ${s.benefits_money}`;
        speakText(speechSummary, effectiveLang);
      };

      dom.sheetBtnSave.onclick = () => {
        toggleSaveScheme(s);
      };

      // WhatsApp share link
      const shareText = encodeURIComponent(
        `🏛️ *${s.scheme_name}*\n💰 Benefit: ${s.benefits_money}\n🔗 Official Portal: ${s.application_url}\n(Shared from Bolo App)`
      );
      dom.sheetBtnWhatsapp.href = `https://wa.me/?text=${shareText}`;

      // Show bottom sheet
      dom.bottomSheetBackdrop.classList.add("active");
      dom.bottomSheetBackdrop.setAttribute("aria-hidden", "false");
    } catch (e) {
      console.error("Error opening scheme details:", e);
    }
  }

  function closeBottomSheet() {
    bargeIn();
    dom.bottomSheetBackdrop.classList.remove("active");
    dom.bottomSheetBackdrop.setAttribute("aria-hidden", "true");
  }

  function renderDocumentsChecklist(schemeId, docsList) {
    dom.sheetDocsChecklist.replaceChildren();
    const storageKey = `bolo_doc_checks_${schemeId}`;
    let savedChecks = {};
    try {
      savedChecks = JSON.parse(localStorage.getItem(storageKey) || "{}");
    } catch (e) {}

    if (docsList.length === 0) {
      const noneItem = document.createElement("div");
      noneItem.textContent = "No specific documents listed.";
      dom.sheetDocsChecklist.appendChild(noneItem);
      return;
    }

    docsList.forEach((docName, idx) => {
      const itemLabel = document.createElement("label");
      itemLabel.className = "checklist-item";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!savedChecks[docName];

      if (cb.checked) itemLabel.classList.add("checked");

      cb.addEventListener("change", () => {
        savedChecks[docName] = cb.checked;
        itemLabel.classList.toggle("checked", cb.checked);
        try {
          localStorage.setItem(storageKey, JSON.stringify(savedChecks));
        } catch (e) {}
      });

      const span = document.createElement("span");
      span.textContent = docName;

      itemLabel.appendChild(cb);
      itemLabel.appendChild(span);
      dom.sheetDocsChecklist.appendChild(itemLabel);
    });
  }

  // ==================== SAVED SCHEMES (BOOKMARKS) ====================
  function getSavedSchemes() {
    try {
      return JSON.parse(localStorage.getItem("bolo_saved_schemes") || "[]");
    } catch (e) {
      return [];
    }
  }

  function toggleSaveScheme(scheme) {
    let saved = getSavedSchemes();
    const existingIdx = saved.findIndex((item) => item.id === scheme.id);

    if (existingIdx >= 0) {
      saved.splice(existingIdx, 1);
    } else {
      saved.push({
        id: scheme.id,
        name: scheme.scheme_name || scheme.name,
        category: scheme.category,
        benefit: scheme.benefits_money || scheme.benefit,
        url: scheme.application_url || scheme.url
      });
    }

    try {
      localStorage.setItem("bolo_saved_schemes", JSON.stringify(saved));
    } catch (e) {}

    updateSaveButtonUI(scheme.id);
    renderSavedScreen();
  }

  function updateSaveButtonUI(schemeId) {
    const saved = getSavedSchemes();
    const isSaved = saved.some((item) => item.id === schemeId);
    dom.sheetBtnSave.classList.toggle("saved", isSaved);
    dom.lblSheetSave.textContent = isSaved ? getT().saved : getT().save;
    dom.sheetBtnSave.querySelector("span").previousSibling.textContent = isSaved ? "❤️ " : "🤍 ";
  }

  function renderSavedScreen() {
    // 1. Saved Schemes
    const saved = getSavedSchemes();
    dom.savedSchemesContainer.replaceChildren();

    if (saved.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = getT().emptySaved;
      dom.savedSchemesContainer.appendChild(empty);
    } else {
      saved.forEach((s) => {
        const card = document.createElement("div");
        card.className = "scheme-card";

        const topRow = document.createElement("div");
        topRow.className = "card-top";

        const catTag = document.createElement("span");
        catTag.className = `cat-tag ${getCategoryColorClass(s.category)}`;
        catTag.textContent = s.category;

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "clear-btn";
        removeBtn.textContent = "❌ Remove";
        removeBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          toggleSaveScheme(s);
        });

        topRow.appendChild(catTag);
        topRow.appendChild(removeBtn);
        card.appendChild(topRow);

        const title = document.createElement("div");
        title.className = "card-title";
        title.textContent = s.name;
        card.appendChild(title);

        if (s.benefit) {
          const benefit = document.createElement("div");
          benefit.className = "benefit-chip";
          benefit.textContent = `💰 ${s.benefit}`;
          card.appendChild(benefit);
        }

        card.addEventListener("click", () => openSchemeDetails(s.id));
        dom.savedSchemesContainer.appendChild(card);
      });
    }

    // 2. Recent Questions
    let questions = [];
    try {
      questions = JSON.parse(localStorage.getItem("bolo_recent_questions") || "[]");
    } catch (e) {}

    dom.recentQuestionsContainer.replaceChildren();

    if (questions.length === 0) {
      const emptyQ = document.createElement("div");
      emptyQ.className = "empty-state";
      emptyQ.textContent = getT().emptyQuestions;
      dom.recentQuestionsContainer.appendChild(emptyQ);
    } else {
      questions.forEach((q) => {
        const chip = document.createElement("div");
        chip.className = "question-chip";
        chip.textContent = q;

        const arrow = document.createElement("span");
        arrow.textContent = "💬 ↗";
        chip.appendChild(arrow);

        chip.addEventListener("click", () => {
          bargeIn();
          switchTab("talk");
          handleUserQuestion(q, effectiveLang);
        });

        dom.recentQuestionsContainer.appendChild(chip);
      });
    }
  }

  // ==================== EVENT LISTENERS ====================
  function setupEventListeners() {
    // Language buttons
    dom.langBtns.forEach((btn) => {
      btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
    });

    // Navigation Tabs
    dom.tabBtnTalk.addEventListener("click", () => switchTab("talk"));
    dom.tabBtnSchemes.addEventListener("click", () => switchTab("schemes"));
    dom.tabBtnSaved.addEventListener("click", () => switchTab("saved"));

    // Reset Chat
    dom.btnNewChat.addEventListener("click", () => {
      bargeIn();
      resetConversation();
    });

    // Voice Orb Click
    dom.orbWrapper.addEventListener("click", () => {
      if (isSpeaking) {
        bargeIn();
        return;
      }
      if (isRecording) {
        stopVoiceRecording();
      } else {
        startVoiceRecording();
      }
    });

    // Stop Bolo Button
    dom.btnStopSpeaking.addEventListener("click", () => {
      bargeIn();
    });

    // Chat text input send
    dom.btnSendText.addEventListener("click", () => {
      const val = dom.chatTextInput.value;
      if (val && val.trim()) {
        dom.chatTextInput.value = "";
        handleUserQuestion(val, effectiveLang);
      }
    });

    dom.chatTextInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        dom.btnSendText.click();
      }
    });

    // Barge-in when user focuses or types in the text input
    dom.chatTextInput.addEventListener("focus", () => {
      if (isSpeaking) bargeIn();
    });

    // Search Schemes input
    let searchDebounce = null;
    dom.schemesSearchInput.addEventListener("input", (e) => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        fetchSchemes(selectedCategoryFilter === "all" ? "" : selectedCategoryFilter, e.target.value);
      }, 300);
    });

    // Clear Recent Questions
    dom.btnClearQuestions.addEventListener("click", () => {
      try {
        localStorage.removeItem("bolo_recent_questions");
        renderSavedScreen();
      } catch (e) {}
    });

    // Bottom Sheet Close
    dom.btnCloseSheet.addEventListener("click", closeBottomSheet);
    dom.bottomSheetBackdrop.addEventListener("click", (e) => {
      if (e.target === dom.bottomSheetBackdrop) {
        closeBottomSheet();
      }
    });

    // Escape key closes modal
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && dom.bottomSheetBackdrop.classList.contains("active")) {
        closeBottomSheet();
      }
    });
  }

  // Network offline / online banner
  function checkNetworkStatus() {
    function updateOnlineStatus() {
      if (!navigator.onLine) {
        dom.bannerOffline.classList.add("active");
      } else {
        dom.bannerOffline.classList.remove("active");
      }
    }
    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    updateOnlineStatus();
  }

  // Service Worker Registration for PWA
  function registerServiceWorker() {
    if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
      navigator.serviceWorker
        .register("./sw.js")
        .then(() => console.log("Bolo Service Worker Registered"))
        .catch((err) => console.log("Service Worker registration skipped:", err));
    }
  }

  // Run app on DOM load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
