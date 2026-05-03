const state = {
  messages: [],
  quizQuestions: [],
  quizIndex: 0,
  quizScore: 0,
  quizTopic: 'Indian election process',
  selectedPhase: 'all',
  isLoading: false,
};

const nextEvent = {
  name: 'Vote Counting Day — All States',
  name_hi: 'मतगणना दिवस — सभी राज्य',
  date: '2026-05-04T08:00:00+05:30',
  windowStart: '2026-04-09T00:00:00+05:30',
};

// ── Global state (must be declared before any function call) ──
let currentLang = localStorage.getItem('electiq_lang') || 'en';
let _electionsData = null;
let _activeElecIdx = null;

function pad2(n) {
  return String(Math.max(0, n)).padStart(2, '0');
}

function buildCalendarLink(event) {
  const start = new Date(event.date);
  if (Number.isNaN(start.getTime())) return '#';
  const y = start.getFullYear();
  const m = pad2(start.getMonth() + 1);
  const d = pad2(start.getDate());
  return 'https://calendar.google.com/calendar/render?action=TEMPLATE' +
    `&text=${encodeURIComponent(event.name)}` +
    `&dates=${y}${m}${d}/${y}${m}${d}` +
    `&details=${encodeURIComponent('Reminder from ElectIQ. Verify official dates with ECI before acting.')}`;
}

function updateCountdown() {
  const eventDate = new Date(nextEvent.date);
  const startDate = new Date(nextEvent.windowStart);
  const now = new Date();
  if (Number.isNaN(eventDate.getTime())) return;
  const diff = Math.max(0, eventDate - now);
  const totalSeconds = Math.floor(diff / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  setText('event-name', currentLang === 'hi' && nextEvent.name_hi ? nextEvent.name_hi : nextEvent.name);
  setText('count-days', pad2(days));
  setText('count-hours', pad2(hours));
  setText('count-mins', pad2(mins));
  setText('count-secs', pad2(secs));

  const progress = document.getElementById('count-progress');
  if (progress) {
    const totalWindow = Math.max(1, eventDate - startDate);
    const elapsed = Math.min(totalWindow, Math.max(0, now - startDate));
    progress.style.width = `${Math.round((elapsed / totalWindow) * 100)}%`;
  }

  const link = document.getElementById('event-calendar-link');
  if (link) link.href = buildCalendarLink(nextEvent);
}
updateCountdown();
window.setInterval(updateCountdown, 1000);

function showSection(id) {
  const section = document.getElementById('section-' + id);
  const nav = document.getElementById('nav-' + id);
  if (!section || !nav) return;
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tabs button').forEach(b => b.classList.remove('active'));
  section.classList.add('active');
  nav.classList.add('active');
  if (id === 'timeline') renderTimeline(state.selectedPhase);
  if (id === 'home' && !_electionsData) loadElections();
}

const timelineData = [
  { phase:'pre', step:'Step 1', color:'', title:'ECI announcement', desc:'The Election Commission announces the schedule, polling phases, nomination deadlines, and counting date. The Model Code of Conduct comes into force from the announcement.', tag:'Schedule and MCC' },
  { phase:'pre', step:'Step 2', color:'', title:'Voter roll revision', desc:'Citizens check their names, apply through Form 6, correct details, and locate their polling station through official voter service portals.', tag:'Registration readiness' },
  { phase:'pre', step:'Step 3', color:'navy', title:'Candidate nomination', desc:'Candidates file nomination papers with the Returning Officer along with affidavits and required deposits.', tag:'Nomination window' },
  { phase:'pre', step:'Step 4', color:'navy', title:'Scrutiny and withdrawal', desc:'Nominations are examined for validity. Candidates may withdraw within the notified window before the final candidate list is published.', tag:'Final candidate list' },
  { phase:'pre', step:'Step 5', color:'', title:'Campaign and silent period', desc:'Campaigning runs under expenditure limits and MCC restrictions. Public campaigning stops during the 48-hour silent period before polling.', tag:'Campaign rules' },
  { phase:'during', step:'Step 6', color:'green', title:'Polling day', desc:'Voters arrive at their assigned booth, verify identity, vote on the EVM, view the VVPAT slip briefly, and receive indelible ink marking.', tag:'Vote casting' },
  { phase:'during', step:'Step 7', color:'green', title:'EVM sealing and strongroom', desc:'After polling, EVMs and VVPATs are sealed in the presence of agents and stored in guarded strongrooms with security protocols.', tag:'Secure storage' },
  { phase:'post', step:'Step 8', color:'navy', title:'Counting begins', desc:'Postal ballots are typically counted first. EVM results are counted in rounds at designated counting centres with candidate agents present.', tag:'Counting centre' },
  { phase:'post', step:'Step 9', color:'navy', title:'Result declaration', desc:'The candidate with the highest valid votes wins under the First Past the Post system. The Returning Officer issues the certificate of election.', tag:'Official result' },
  { phase:'post', step:'Step 10', color:'green', title:'Government formation', desc:'For assembly or Lok Sabha elections, the leader who commands majority support is invited to form the government and take oath.', tag:'After results' },
];

function renderTimeline(phase) {
  const container = document.getElementById('timeline-container');
  const filtered = phase === 'all' ? timelineData : timelineData.filter(t => t.phase === phase);
  container.innerHTML = filtered.map(t => `
    <div class="tl-item">
      <div class="tl-dot ${t.color}"></div>
      <div class="card tl-card">
        <div class="tl-step">${t.step}</div>
        <div class="tl-title">${t.title}</div>
        <div class="tl-desc">${t.desc}</div>
        <span class="tl-tag">${t.tag}</span>
      </div>
    </div>
  `).join('');
}
function showPhase(phase, btn) {
  state.selectedPhase = phase;
  document.querySelectorAll('.phase-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTimeline(phase);
}
renderTimeline('all');

function escHtml(t) {
  return String(t ?? '')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}
function formatMarkdown(text) {
  return escHtml(text)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^### (.*)/gm, '<h4>$1</h4>')
    .replace(/^## (.*)/gm, '<h3>$1</h3>')
    .replace(/^# (.*)/gm, '<h2>$1</h2>')
    .replace(/^\d+\. (.*)/gm, '<li>$1</li>')
    .replace(/^[-*] (.*)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}
function avatarSvg() {
  return '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M12 3v18M3 12h18" stroke="currentColor" stroke-width="2"/></svg>';
}
function addMsg(role, content) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.innerHTML = `<div class="msg-avatar">${avatarSvg()}</div><div class="msg-bubble">${role === 'assistant' ? formatMarkdown(content) : escHtml(content)}</div>`;
  document.getElementById('chat-messages').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'end' });
}
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
}
function askQuick(q) {
  document.getElementById('chat-input').value = q;
  sendMessage();
}
function askAbout(q) {
  showSection('chat');
  window.setTimeout(() => {
    document.getElementById('chat-input').value = q;
    sendMessage();
  }, 150);
}
async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text || state.isLoading) return;
  state.messages.push({ role: 'user', content: text });
  addMsg('user', text);
  input.value = '';
  input.style.height = 'auto';
  state.isLoading = true;
  document.getElementById('send-btn').disabled = true;

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: state.messages })
    });
    if (!res.ok || !res.body) {
      const fallback = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: state.messages })
      });
      const data = await fallback.json();
      const reply = data.response || data.error || 'Sorry, I could not complete that request.';
      state.messages.push({ role: 'assistant', content: reply });
      addMsg('assistant', reply);
      return;
    }

    const el = document.createElement('div');
    el.className = 'msg assistant';
    const bubbleId = `stream-bubble-${Date.now()}`;
    el.innerHTML = `<div class="msg-avatar">${avatarSvg()}</div><div class="msg-bubble" id="${bubbleId}"><span class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span></div>`;
    document.getElementById('chat-messages').appendChild(el);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let pending = '';
    let streamDone = false;
    const bubble = document.getElementById(bubbleId);

    while (!streamDone) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      const lines = pending.split('\n');
      pending = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') { streamDone = true; break; }
        try {
          const parsed = JSON.parse(payload);
          if (parsed.text) {
            fullText += parsed.text;
            bubble.innerHTML = formatMarkdown(fullText);
            el.scrollIntoView({ behavior: 'smooth', block: 'end' });
          }
          if (parsed.error) {
            fullText = parsed.error;
            bubble.textContent = parsed.error;
            streamDone = true;
            break;
          }
        } catch (err) {}
      }
    }
    bubble.removeAttribute('id');
    if (fullText) {
      if (currentLang === 'hi') {
        bubble.innerHTML = '<span class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>';
        try {
          const transRes = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: fullText, target: 'hi' })
          });
          const transData = await transRes.json();
          if (transData.translated) fullText = transData.translated;
        } catch(e) {}
        bubble.innerHTML = formatMarkdown(fullText);
        el.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
      state.messages.push({ role: 'assistant', content: fullText });
    }
  } catch (e) {
    addMsg('assistant', 'Connection error. Please try again.');
  } finally {
    state.isLoading = false;
    document.getElementById('send-btn').disabled = false;
  }
}

function selectTopic(btn, topic) {
  document.querySelectorAll('.topic-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  state.quizTopic = topic;
}
async function startQuiz() {
  document.getElementById('quiz-setup').style.display = 'none';
  document.getElementById('quiz-result').style.display = 'none';
  document.getElementById('quiz-loading').style.display = 'flex';
  try {
    const res = await fetch('/api/quiz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: state.quizTopic })
    });
    const data = await res.json();
    if (!Array.isArray(data.questions) || !data.questions.length) throw new Error(data.error || 'No questions returned');
    state.quizQuestions = data.questions;
    state.quizIndex = 0;
    state.quizScore = 0;
    document.getElementById('quiz-loading').style.display = 'none';
    document.getElementById('quiz-play').style.display = 'block';
    renderQuestion();
  } catch (e) {
    alert('Could not load quiz. Please try again.');
    document.getElementById('quiz-loading').style.display = 'none';
    document.getElementById('quiz-setup').style.display = 'block';
  }
}
function renderQuestion() {
  const q = state.quizQuestions[state.quizIndex];
  const total = state.quizQuestions.length;
  if (!q || !Array.isArray(q.options) || !q.options.length) {
    restartQuiz();
    return;
  }
  document.getElementById('progress-fill').style.width = `${(state.quizIndex / total) * 100}%`;
  document.getElementById('progress-text').textContent = `${state.quizIndex + 1} / ${total}`;
  document.getElementById('quiz-question').textContent = q.question;
  document.getElementById('quiz-score').textContent = state.quizScore;
  document.getElementById('quiz-total').textContent = total;
  document.getElementById('quiz-explanation').style.display = 'none';
  document.getElementById('next-btn').style.display = 'none';
  document.getElementById('quiz-options').innerHTML = q.options.map((opt, i) => `<button class="option-btn" onclick="selectAnswer(${i})">${escHtml(opt)}</button>`).join('');
}
function selectAnswer(idx) {
  const q = state.quizQuestions[state.quizIndex];
  const btns = document.querySelectorAll('.option-btn');
  if (!q || !btns.length || q.correct < 0 || q.correct >= btns.length) return;
  btns.forEach(b => b.disabled = true);
  btns[q.correct].classList.add('correct');
  if (idx === q.correct) state.quizScore++;
  else if (btns[idx]) btns[idx].classList.add('wrong');
  const exp = document.getElementById('quiz-explanation');
  exp.textContent = q.explanation || '';
  exp.style.display = 'block';
  document.getElementById('next-btn').style.display = 'inline-flex';
  document.getElementById('quiz-score').textContent = state.quizScore;
}
function nextQuestion() {
  state.quizIndex++;
  if (state.quizIndex >= state.quizQuestions.length) showResult();
  else renderQuestion();
}
function showResult() {
  document.getElementById('quiz-play').style.display = 'none';
  document.getElementById('quiz-result').style.display = 'block';
  const total = state.quizQuestions.length;
  const pct = total ? state.quizScore / total : 0;
  document.getElementById('result-score').textContent = `${state.quizScore}/${total}`;
  document.getElementById('result-msg').textContent = pct >= .8 ? 'Strong civic knowledge.' : pct >= .6 ? 'Good base. Review the timeline for more detail.' : 'Keep learning with the assistant and try again.';
  
  // Submit score
  fetch('/api/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: state.quizTopic, score: state.quizScore, total: total })
  }).catch(() => {});
}
function restartQuiz() {
  document.getElementById('quiz-result').style.display = 'none';
  document.getElementById('quiz-setup').style.display = 'block';
}

function setFcClaim(text) {
  document.getElementById('fc-claim').value = text;
}
async function verifyFact() {
  const claim = document.getElementById('fc-claim').value.trim();
  if (!claim || claim.length < 10) {
    document.getElementById('fc-status').textContent = 'Enter a meaningful claim first.';
    return;
  }
  document.getElementById('fc-result').style.display = 'none';
  document.getElementById('fc-loading').style.display = 'flex';
  document.getElementById('fc-verify-btn').disabled = true;
  document.getElementById('fc-status').textContent = '';
  try {
    const res = await fetch('/api/fact-check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ claim })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const cls = ({ TRUE:'true', FALSE:'false', MISLEADING:'misleading', 'PARTIALLY TRUE':'partially', UNVERIFIED:'unverified' })[data.verdict] || 'unverified';
    document.getElementById('fc-emoji').textContent = verdictSymbol(data.verdict);
    const verdictEl = document.getElementById('fc-verdict');
    verdictEl.textContent = data.verdict || 'UNVERIFIED';
    verdictEl.className = 'fc-verdict-label ' + cls;
    document.getElementById('fc-summary').textContent = data.summary || '';
    document.getElementById('fc-explanation').innerHTML = escHtml(data.explanation || '').replace(/\n/g, '<br>');
    let srcHtml = '';
    (data.sources || []).forEach(s => { srcHtml += `<div class="fc-source-item">${escHtml(s)}</div>`; });
    (data.grounding_sources || []).forEach(s => { srcHtml += `<div class="fc-source-item"><a href="${escHtml(s.url || '#')}" target="_blank" rel="noopener">${escHtml(s.title || s.url || 'Source')}</a></div>`; });
    document.getElementById('fc-sources-container').innerHTML = srcHtml;
    document.getElementById('fc-related-container').innerHTML = (data.related_facts || []).map(f => `<span class="fc-related-item">${escHtml(f)}</span>`).join('');
    document.getElementById('fc-result').style.display = 'block';
  } catch (e) {
    document.getElementById('fc-status').textContent = e.message || 'Network error. Please try again.';
  } finally {
    document.getElementById('fc-loading').style.display = 'none';
    document.getElementById('fc-verify-btn').disabled = false;
  }
}
function verdictSymbol(v) {
  if (v === 'TRUE') return 'T';
  if (v === 'FALSE') return 'F';
  if (v === 'MISLEADING') return '!';
  if (v === 'PARTIALLY TRUE') return 'P';
  return '?';
}

const calEvents = [
  { title:'Check voter registration status', date:'2026-01-15', note:'Verify your name in the electoral roll on the official voter portal.' },
  { title:'Review voter ID documents', date:'2026-02-10', note:'Check accepted identity documents before polling day.' },
  { title:'Track ECI schedule announcement', date:'2026-03-01', note:'Follow official ECI notifications for schedules and MCC updates.' },
  { title:'Find polling station', date:'2026-04-01', note:'Confirm polling booth and route before election day.' },
];
function makeGCalLink(event) {
  const d = String(event.date || '').replace(/-/g,'');
  if (!/^\d{8}$/.test(d)) return '#';
  return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(event.title)}&dates=${d}/${d}&details=${encodeURIComponent(event.note)}`;
}
function openCalModal() {
  document.getElementById('cal-events').innerHTML = calEvents.map(ev => `
    <div class="cal-event">
      <div><div class="cal-event-title">${escHtml(ev.title)}</div><div class="cal-event-date">${new Date(ev.date).toLocaleDateString('en-IN', { day:'numeric', month:'long', year:'numeric' })}</div></div>
      <a href="${makeGCalLink(ev)}" target="_blank" rel="noopener"><button class="cal-add-btn">Add</button></a>
    </div>
  `).join('');
  document.getElementById('cal-modal').classList.add('open');
}
function closeCal(e) {
  if (e.target.id === 'cal-modal') document.getElementById('cal-modal').classList.remove('open');
}

// ══════════════════════════════════════════════
// LANGUAGE TOGGLE  (EN / HI)
// ══════════════════════════════════════════════
const TRANSLATIONS = {
  en: {
    nav_home:'Overview', nav_timeline:'Election Flow', nav_chat:'Ask AI',
    nav_factcheck:'Fact Check', nav_quiz:'Quiz', nav_resources:'Resources',
    hero_kicker:'Non-partisan civic assistant',
    hero_heading:'Understand Indian elections with clarity.',
    hero_lead:'ElectIQ turns voter registration, EVM/VVPAT, polling day rules, counting, and official election resources into simple, verifiable guidance for citizens and first-time voters.',
    btn_ask:'Ask ElectIQ', btn_verify:'Verify a Claim', btn_dates:'Save Dates',
    trust_neutral:'Neutral by design', trust_plain:'Plain-language answers', trust_official:'Official-source oriented',
    tracker_now:'🗳️ Elections Happening Now', tracker_now_sub:'Click any state for schedule details & key dates',
    tracker_upcoming:'📅 Upcoming Elections', tracker_upcoming_sub:'Confirmed elections in the next 12 months',
    detail_type:'Election Type', detail_seats:'Total Seats', detail_poll:'Polling Date', detail_count:'Counting Date',
    metric_elections:'Lok Sabha, Vidhan Sabha, Rajya Sabha, municipal, and panchayat basics.',
    metric_tools:'AI guide, timeline, quiz generator, and grounded fact-checking.',
    metric_links:'Designed around official and non-partisan public information.',
    metric_style:'Clear answers for citizens, students, and first-time voters.',
    chat_placeholder:'Ask a question about Indian elections...',
    quick_q1:'How do I check my name in the voter list?',
    quick_q2:'What is the Model Code of Conduct?',
    quick_q3:'What ID documents are accepted at a polling booth?',
    quick_q4:'What is NOTA and when can voters use it?',
    fc_placeholder:'Example: VVPAT slips are counted for every polling station in India.',
    event_name_fallback:'Next Election Event',
  },
  hi: {
    nav_home:'सारांश', nav_timeline:'चुनाव प्रक्रिया', nav_chat:'AI से पूछें',
    nav_factcheck:'तथ्य जाँच', nav_quiz:'क्विज़', nav_resources:'संसाधन',
    hero_kicker:'निष्पक्ष नागरिक सहायक',
    hero_heading:'भारतीय चुनावों को स्पष्टता से समझें।',
    hero_lead:'ElectIQ मतदाता पंजीकरण, EVM/VVPAT, मतदान दिवस नियम, मतगणना और आधिकारिक चुनाव संसाधनों को नागरिकों और पहली बार मतदाताओं के लिए सरल, सत्यापन योग्य मार्गदर्शन में बदलता है।',
    btn_ask:'ElectIQ से पूछें', btn_verify:'दावा सत्यापित करें', btn_dates:'तिथियाँ सहेजें',
    trust_neutral:'निष्पक्ष डिज़ाइन', trust_plain:'सरल भाषा में उत्तर', trust_official:'आधिकारिक स्रोत आधारित',
    tracker_now:'🗳️ अभी हो रहे चुनाव', tracker_now_sub:'अनुसूची और मुख्य तिथियों के लिए किसी राज्य पर क्लिक करें',
    tracker_upcoming:'📅 आगामी चुनाव', tracker_upcoming_sub:'अगले 12 महीनों के पुष्टि किए गए चुनाव',
    detail_type:'चुनाव प्रकार', detail_seats:'कुल सीटें', detail_poll:'मतदान तिथि', detail_count:'मतगणना तिथि',
    metric_elections:'लोकसभा, विधानसभा, राज्यसभा, नगर निगम और पंचायत की मूल बातें।',
    metric_tools:'AI गाइड, टाइमलाइन, क्विज़ जेनरेटर और तथ्य-जाँच।',
    metric_links:'आधिकारिक और निष्पक्ष सार्वजनिक जानकारी पर आधारित।',
    metric_style:'नागरिकों, छात्रों और पहली बार मतदाताओं के लिए स्पष्ट उत्तर।',
    chat_placeholder:'भारतीय चुनावों के बारे में प्रश्न पूछें...',
    quick_q1:'मैं मतदाता सूची में अपना नाम कैसे देखूँ?',
    quick_q2:'आदर्श आचार संहिता क्या है?',
    quick_q3:'मतदान केंद्र पर कौन से ID दस्तावेज़ स्वीकार किए जाते हैं?',
    quick_q4:'NOTA क्या है और मतदाता इसका उपयोग कब कर सकते हैं?',
    fc_placeholder:'उदाहरण: भारत में VVPAT पर्चियाँ प्रत्येक मतदान केंद्र के लिए गिनी जाती हैं।',
    event_name_fallback:'अगली चुनाव घटना',
  }
};

// (currentLang, _electionsData, _activeElecIdx declared at top of script)

function setLang(lang) {
  if (!TRANSLATIONS[lang]) lang = 'en';
  currentLang = lang;
  localStorage.setItem('electiq_lang', lang);
  // Toggle button states
  document.getElementById('lang-en').classList.toggle('active', lang === 'en');
  document.getElementById('lang-hi').classList.toggle('active', lang === 'hi');
  document.getElementById('lang-en').setAttribute('aria-pressed', lang === 'en');
  document.getElementById('lang-hi').setAttribute('aria-pressed', lang === 'hi');
  // Apply all data-i18n text nodes
  const t = TRANSLATIONS[lang];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (t[key] !== undefined) el.textContent = t[key];
  });
  // Dynamic targets
  const inp = document.getElementById('chat-input');
  if (inp) inp.placeholder = t.chat_placeholder;
  const fc = document.getElementById('fc-claim');
  if (fc) fc.placeholder = t.fc_placeholder;
  // Quick questions
  const qqs = document.querySelectorAll('.quick-q');
  const qqKeys = ['quick_q1','quick_q2','quick_q3','quick_q4'];
  qqs.forEach((el, i) => { if (qqKeys[i] && t[qqKeys[i]]) el.textContent = t[qqKeys[i]]; });
  updateCountdown();
  if (_electionsData) {
    renderCurrentElections(_electionsData.current || []);
    renderUpcomingElections(_electionsData.upcoming || []);
    if (_activeElecIdx !== null) openDetail(_activeElecIdx);
  }
}
// Apply saved language on load
setLang(currentLang);

// ══════════════════════════════════════════════
// LIVE ELECTION TRACKER
// ══════════════════════════════════════════════
const STATUS_LABELS = {
  en: { voting_today:'Voting Today', voting_soon:'Voting Soon', counting:'Counting', results_out:'Results Out' },
  hi: { voting_today:'आज मतदान', voting_soon:'जल्द मतदान', counting:'मतगणना', results_out:'परिणाम घोषित' }
};

async function loadElections() {
  try {
    const res = await fetch('/api/elections');
    if (!res.ok) throw new Error('API error');
    _electionsData = await res.json();
    renderCurrentElections(_electionsData.current || []);
    renderUpcomingElections(_electionsData.upcoming || []);
    // Update countdown with live event from API
    if (_electionsData.next_major_event) {
      const ev = _electionsData.next_major_event;
      nextEvent.name = ev.name || TRANSLATIONS.en.event_name_fallback;
      nextEvent.name_hi = ev.name_hi || '';
      if (ev.date_iso) nextEvent.date = ev.date_iso;
      nextEvent.windowStart = new Date().toISOString();
      updateCountdown();
    }
  } catch (e) {
    document.getElementById('current-elections-row').innerHTML =
      '<p style="color:var(--muted);padding:12px;" data-i18n="tracker_error">Could not load live election data. Check ECI.gov.in for latest schedules.</p>';
    document.getElementById('upcoming-elections-list').innerHTML = '';
  }
}

function renderCurrentElections(elections) {
  const row = document.getElementById('current-elections-row');
  if (!row) return;
  if (!elections.length) {
    row.innerHTML = '<p style="color:var(--muted);padding:12px;">No elections currently in progress.</p>';
    return;
  }
  row.innerHTML = elections.map((e, i) => {
    const slang = STATUS_LABELS[currentLang]?.[e.status] || e.status_label || e.status;
    return `<button class="elec-card" onclick="openDetail(${i})" aria-label="${escHtml(e.state)} election details">
      <div class="elec-state">${escHtml(e.state)}</div>
      <div class="elec-state-hi">${escHtml(e.state_hi || '')}</div>
      <div class="elec-type">${escHtml(e.election_type || '')}</div>
      <div class="elec-date">${escHtml(e.polling_date || '')}</div>
      <div class="elec-note">${escHtml(e.note || '')}</div>
      <div class="status-badge ${escHtml(e.status || '')}"><span class="status-dot-sm"></span>${escHtml(slang)}</div>
    </button>`;
  }).join('');
}

function renderUpcomingElections(upcoming) {
  const list = document.getElementById('upcoming-elections-list');
  if (!list) return;
  if (!upcoming.length) { list.innerHTML = ''; return; }
  list.innerHTML = upcoming.map(u => `
    <div class="upcoming-row">
      <div>
        <div class="upcoming-state">${escHtml(u.state)}</div>
        <div class="upcoming-state-hi">${escHtml(u.state_hi || '')} &mdash; ${escHtml(u.election_type || '')}</div>
      </div>
      <div class="upcoming-period">${escHtml(u.expected_period || '')} &bull; ${u.total_seats || '?'} seats</div>
    </div>`).join('');
}

function openDetail(idx) {
  if (!_electionsData || !_electionsData.current || !_electionsData.current[idx]) return;
  _activeElecIdx = idx;
  const e = _electionsData.current[idx];
  // Highlight active card
  document.querySelectorAll('.elec-card').forEach((c, i) => c.classList.toggle('active', i === idx));
  document.getElementById('detail-state').textContent = e.state;
  document.getElementById('detail-state-hi').textContent = e.state_hi || '';
  document.getElementById('detail-type').textContent = e.election_type || '—';
  document.getElementById('detail-seats').textContent = e.total_seats ? `${e.total_seats} seats` : '—';
  document.getElementById('detail-poll').textContent = e.polling_date || '—';
  document.getElementById('detail-count').textContent = e.counting_date || '—';
  const badge = document.getElementById('detail-status-badge');
  badge.className = `status-badge ${e.status || ''}`;
  badge.innerHTML = `<span class="status-dot-sm"></span><span id="detail-status-label">${escHtml(STATUS_LABELS[currentLang]?.[e.status] || e.status_label || e.status)}</span>`;
  const panel = document.getElementById('elec-detail');
  panel.classList.add('open');
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeDetail() {
  document.getElementById('elec-detail').classList.remove('open');
  document.querySelectorAll('.elec-card').forEach(c => c.classList.remove('active'));
  _activeElecIdx = null;
}

function askAboutElection() {
  if (_activeElecIdx === null || !_electionsData) return;
  const e = _electionsData.current[_activeElecIdx];
  const q = currentLang === 'hi'
    ? `${e.state} में ${e.election_type || 'विधानसभा'} चुनाव के बारे में बताएं — कार्यक्रम, चरण और मुख्य तथ्य।`
    : `Tell me about the ${e.election_type || 'Assembly'} election in ${e.state} — schedule, phases, and key facts.`;
  askAbout(q);
}

async function loadAnalytics() {
  const container = document.getElementById('trending-topics-list');
  if (!container) return;
  try {
    const res = await fetch('/api/analytics');
    if (!res.ok) throw new Error();
    const data = await res.json();
    if (data.top_topics && data.top_topics.length) {
      container.innerHTML = data.top_topics.map(t => 
        `<div class="quick-q" onclick="askQuick('${escHtml(t.topic)}')">${escHtml(t.topic)} <span style="opacity:0.5;font-size:0.8em">(${t.count})</span></div>`
      ).join('');
    }
  } catch(e) {
    // Silent fail if analytics unavailable
  }
}

// Auto-load elections and analytics on initial render
loadElections();
loadAnalytics();