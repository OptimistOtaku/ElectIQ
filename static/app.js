/**
 * ElectIQ Frontend Logic (v3.1 Refactored)
 * Handles interactive UI, AI streaming, localization, and accessibility.
 */

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

// ── Global state ──
let currentLang = localStorage.getItem('electiq_lang') || 'en';
let _electionsData = null;
let _activeElecIdx = null;

/**
 * Utility: Pad single digit numbers with zero.
 */
function pad2(n) {
  return String(Math.max(0, n)).padStart(2, '0');
}

/**
 * Focus Trap Utility for Modals.
 * Ensures tabbing remains inside the modal when open.
 */
function trapFocus(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  const focusableEls = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const first = focusableEls[0];
  const last = focusableEls[focusableEls.length - 1];

  modal.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
}

/**
 * Builds a Google Calendar template link.
 */
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

/**
 * Updates the hero section countdown timer.
 */
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

/**
 * Navigation handler to switch between dashboard sections.
 */
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

/**
 * Renders the election lifecycle timeline.
 */
const timelineData = [
  { phase:'pre', step:'Step 1', color:'', title:'ECI announcement', desc:'The Election Commission announces the schedule and MCC comes into force.', tag:'Schedule and MCC' },
  { phase:'pre', step:'Step 2', color:'', title:'Voter roll revision', desc:'Citizens check names and apply via official portals.', tag:'Registration' },
  { phase:'pre', step:'Step 3', color:'navy', title:'Candidate nomination', desc:'Candidates file papers and affidavits with the Returning Officer.', tag:'Nomination' },
  { phase:'pre', step:'Step 4', color:'navy', title:'Scrutiny and withdrawal', desc:'Nominations are examined; final candidate list is published.', tag:'Final list' },
  { phase:'pre', step:'Step 5', color:'', title:'Campaign and silent period', desc:'Public campaigning stops 48 hours before polling.', tag:'Campaign' },
  { phase:'during', step:'Step 6', color:'green', title:'Polling day', desc:'Voters verify identity, vote on EVM, and view VVPAT slip.', tag:'Vote casting' },
  { phase:'during', step:'Step 7', color:'green', title:'EVM sealing', desc:'EVMs are sealed and stored in guarded strongrooms.', tag:'Secure storage' },
  { phase:'post', step:'Step 8', color:'navy', title:'Counting begins', desc:'EVM results are counted in rounds at designated centres.', tag:'Counting' },
  { phase:'post', step:'Step 9', color:'navy', title:'Result declaration', desc:'Winning certificates are issued by the Returning Officer.', tag:'Result' },
  { phase:'post', step:'Step 10', color:'green', title:'Government formation', desc:'The majority leader is invited to form the government.', tag:'Oath' },
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

/**
 * Changes timeline view phase.
 */
function showPhase(phase, btn) {
  state.selectedPhase = phase;
  document.querySelectorAll('.phase-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTimeline(phase);
}

/**
 * Escapes HTML to prevent XSS.
 */
function escHtml(t) {
  return String(t ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/**
 * Minimal markdown formatter for AI responses.
 */
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

/**
 * Chat avatar SVG generator.
 */
function avatarSvg() {
  return '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M12 3v18M3 12h18" stroke="currentColor" stroke-width="2"/></svg>';
}

/**
 * Appends a message to the chat container.
 */
function addMsg(role, content) {
  const el = document.createElement('div');
  el.className = `msg ${role}`;
  el.innerHTML = `<div class="msg-avatar">${avatarSvg()}</div><div class="msg-bubble">${role === 'assistant' ? formatMarkdown(content) : escHtml(content)}</div>`;
  document.getElementById('chat-messages').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

/**
 * Core: Sends message to the streaming API.
 */
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
    if (!res.ok || !res.body) throw new Error('API Unavailable');

    const el = document.createElement('div');
    el.className = 'msg assistant';
    const bubbleId = `stream-bubble-${Date.now()}`;
    el.innerHTML = `<div class="msg-avatar">${avatarSvg()}</div><div class="msg-bubble" id="${bubbleId}"><span class="typing-indicator" role="status" aria-live="polite"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span></div>`;
    document.getElementById('chat-messages').appendChild(el);
    
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '', pending = '', streamDone = false;
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
          if (parsed.text) { fullText += parsed.text; bubble.innerHTML = formatMarkdown(fullText); el.scrollIntoView({ behavior: 'smooth', block: 'end' }); }
        } catch (err) {}
      }
    }
    
    bubble.removeAttribute('id');
    // Tier 2: Translation hook for localized sessions
    if (fullText && currentLang === 'hi') {
      bubble.innerHTML = '<span class="typing-indicator" role="status"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>';
      try {
        const transRes = await fetch('/api/translate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:fullText, target:'hi'})});
        const transData = await transRes.json();
        if (transData.translated) fullText = transData.translated;
      } catch(e) {}
      bubble.innerHTML = formatMarkdown(fullText);
    }
    state.messages.push({ role: 'assistant', content: fullText });
  } catch (e) {
    addMsg('assistant', 'Connection error. Please try again.');
  } finally {
    state.isLoading = false;
    document.getElementById('send-btn').disabled = false;
  }
}

/**
 * Quiz system handlers.
 */
async function startQuiz() {
  document.getElementById('quiz-setup').style.display = 'none';
  document.getElementById('quiz-loading').style.display = 'flex';
  try {
    const res = await fetch('/api/quiz', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({topic: state.quizTopic})});
    const data = await res.json();
    state.quizQuestions = data.questions || [];
    state.quizIndex = 0; state.quizScore = 0;
    document.getElementById('quiz-loading').style.display = 'none';
    document.getElementById('quiz-play').style.display = 'block';
    renderQuestion();
  } catch (e) {
    restartQuiz();
  }
}

function renderQuestion() {
  const q = state.quizQuestions[state.quizIndex];
  const total = state.quizQuestions.length;
  document.getElementById('progress-fill').style.width = `${(state.quizIndex / total) * 100}%`;
  document.getElementById('progress-text').textContent = `${state.quizIndex + 1} / ${total}`;
  document.getElementById('quiz-question').textContent = q.question;
  document.getElementById('quiz-options').innerHTML = q.options.map((opt, i) => `<button type="button" class="option-btn" onclick="selectAnswer(${i})">${escHtml(opt)}</button>`).join('');
}

function selectAnswer(idx) {
  const q = state.quizQuestions[state.quizIndex];
  const btns = document.querySelectorAll('.option-btn');
  btns.forEach(b => b.disabled = true);
  btns[q.correct].classList.add('correct');
  if (idx === q.correct) state.quizScore++; else if (btns[idx]) btns[idx].classList.add('wrong');
  const exp = document.getElementById('quiz-explanation');
  exp.textContent = q.explanation || ''; exp.style.display = 'block';
  document.getElementById('next-btn').style.display = 'inline-flex';
}

/**
 * Fact-checker UI handler.
 */
async function verifyFact() {
  const claim = document.getElementById('fc-claim').value.trim();
  if (claim.length < 10) return;
  document.getElementById('fc-loading').style.display = 'flex';
  try {
    const res = await fetch('/api/fact-check', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({claim})});
    const data = await res.json();
    document.getElementById('fc-verdict').textContent = data.verdict;
    document.getElementById('fc-explanation').innerHTML = formatMarkdown(data.explanation || '');
    document.getElementById('fc-result').style.display = 'block';
  } finally {
    document.getElementById('fc-loading').style.display = 'none';
  }
}

/**
 * Localization logic.
 */
function setLang(lang) {
  currentLang = lang;
  localStorage.setItem('electiq_lang', lang);
  document.getElementById('lang-en').classList.toggle('active', lang === 'en');
  document.getElementById('lang-hi').classList.toggle('active', lang === 'hi');
  updateCountdown();
  if (_electionsData) renderCurrentElections(_electionsData.current || []);
}

// Init
window.onload = () => {
  setLang(currentLang);
  updateCountdown();
  window.setInterval(updateCountdown, 1000);
  loadElections();
  loadAnalytics();
};