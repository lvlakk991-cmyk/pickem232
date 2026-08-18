const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand();
  try { tg.setHeaderColor('#070a10'); tg.setBackgroundColor('#070a10'); } catch (e) {}
}

// For local browser testing outside Telegram, set DEV_USER_ID in localStorage, e.g.:
//   localStorage.setItem('DEV_USER_ID', '111111111')
const DEV_USER_ID = localStorage.getItem('DEV_USER_ID') || '';

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers, {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': tg ? tg.initData : '',
  });
  if (DEV_USER_ID) headers['X-Dev-User-Id'] = DEV_USER_ID;

  const res = await fetch(`/api${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const content = document.getElementById('content');
const pointsValue = document.getElementById('pointsValue');
const adminNavBtn = document.getElementById('adminNavBtn');

let state = { tab: 'pickem', isAdmin: false };

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// ------------------------------------------------------------- navigation
document.querySelectorAll('.navbtn').forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.navbtn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
  render();
}

async function bootstrap() {
  try {
    const me = await api('/me');
    pointsValue.textContent = me.points;
    state.isAdmin = me.is_admin;
    state.me = me;
    adminNavBtn.style.display = me.is_admin ? 'flex' : 'none';
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><span class="emoji">⚠️</span>${escapeHtml(e.message)}</div>`;
    return;
  }
  render();
}

async function render() {
  if (state.tab === 'pickem') return renderPickem();
  if (state.tab === 'daily') return renderDaily();
  if (state.tab === 'top') return renderTop();
  if (state.tab === 'stats') return renderStats();
  if (state.tab === 'admin') return renderAdmin();
}

// ------------------------------------------------------------------ gate
function renderGate(me) {
  const rows = me.channels.map((ch) => `
    <a class="channel-link-row" href="https://t.me/${ch.username.replace('@', '')}" target="_blank">
      <span class="name">⭐ ${escapeHtml(ch.name)}</span>
      <span class="partner-status ${ch.subscribed ? 'ok' : 'no'}">${ch.subscribed ? '✓ подписан' : 'подписаться'}</span>
    </a>`).join('');
  return `
    <div class="gate-card">
      ⚠️ Для участия в Pick'em необходимо подписаться на <b>наших партнёров</b>.
      Подпишитесь на все каналы и нажмите «Проверить подписку».
    </div>
    ${rows}
    <button class="btn-primary" id="checkSubBtn">✅ Я подписался — проверить</button>
  `;
}

// --------------------------------------------------------------- pickem
async function renderPickem() {
  content.innerHTML = `<div class="empty-state">Загрузка…</div>`;
  const me = await api('/me');
  pointsValue.textContent = me.points;

  if (me.needs_subscription) {
    content.innerHTML = renderGate(me);
    document.getElementById('checkSubBtn').addEventListener('click', async () => {
      showToast('Проверяем подписку…');
      await renderPickem();
    });
    return;
  }

  const data = await api('/pickem');
  if (!data.tournament) {
    content.innerHTML = `<div class="empty-state"><span class="emoji">🎯</span>Сейчас нет активного турнира.<br>Загляните позже!</div>`;
    return;
  }

  const pct = Math.min(100, Math.round((data.progress / data.max_tier_points) * 100));
  const tierEmojis = { BEGINNER: '🥉', PRO: '🥈', CHEATER: '🥇', GOD: '💎' };
  const tiersHtml = data.tiers.map((t) => `
    <div class="tier ${data.progress >= t.points ? 'reached' : ''}">
      <span class="tier-emoji">${tierEmojis[t.name] || '🏅'}</span>
      <div class="tier-name">${t.name}</div>
      <div class="tier-pts">${t.points} PTS</div>
    </div>`).join('');

  const matchesHtml = data.matches.length
    ? data.matches.map((m) => `
        <div class="match-card" data-match='${JSON.stringify(m).replace(/'/g, "&apos;")}'>
          <div>
            <div class="match-teams">${escapeHtml(m.team1)}<span class="vs">vs</span>${escapeHtml(m.team2)}</div>
            ${m.match_time ? `<div class="match-time">🕒 ${escapeHtml(m.match_time)}</div>` : ''}
          </div>
          <div class="match-cta ${m.predicted ? 'done' : 'open'}">${m.predicted ? '✓ Готово' : '🔮 Предсказать'}</div>
        </div>`).join('')
    : `<div class="empty-state">МАТЧЕЙ ПОКА НЕТ</div>`;

  content.innerHTML = `
    <div class="tournament-card">
      <div class="tournament-top">
        <div class="trophy-icon">🏆</div>
        <div>
          <div class="tournament-name">${escapeHtml(data.tournament.name)}</div>
          <div class="tournament-stage">${escapeHtml(data.tournament.stage)}</div>
        </div>
      </div>
      <div class="progress-header"><span>ПРОГРЕСС ДОСТИЖЕНИЯ</span><span class="val">${data.progress} / ${data.max_tier_points} PTS</span></div>
      <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
      <div class="tiers-row">${tiersHtml}</div>
    </div>
    <div class="section-title">Матчи</div>
    ${matchesHtml}
  `;

  content.querySelectorAll('.match-card').forEach((el) => {
    el.addEventListener('click', () => {
      const match = JSON.parse(el.dataset.match.replace(/&apos;/g, "'"));
      if (!match.predicted) openPredictionSheet(match);
    });
  });
}

function openPredictionSheet(match) {
  const wrap = document.createElement('div');
  wrap.className = 'sheet-backdrop';
  wrap.innerHTML = `
    <div class="sheet">
      <div class="sheet-title">${escapeHtml(match.team1)} vs ${escapeHtml(match.team2)}</div>
      <div class="sheet-sub">Сделайте предсказание — очки начислятся после матча</div>

      <div class="field-label">Победитель</div>
      <div class="team-choice">
        <button class="team-btn" data-winner="${escapeHtml(match.team1)}">${escapeHtml(match.team1)}</button>
        <button class="team-btn" data-winner="${escapeHtml(match.team2)}">${escapeHtml(match.team2)}</button>
      </div>

      <div class="field-label">Точный счёт</div>
      <div class="score-row">
        <input class="score-input" type="number" min="0" id="score1" placeholder="0">
        <span class="score-sep">:</span>
        <input class="score-input" type="number" min="0" id="score2" placeholder="0">
      </div>

      <div class="field-label">MVP матча</div>
      <input class="text-input" type="text" id="mvpInput" placeholder="Ник игрока">

      <button class="btn-primary" id="submitPrediction" disabled>Сохранить предсказание</button>
      <button class="btn-secondary" id="cancelSheet">Отмена</button>
    </div>
  `;
  document.body.appendChild(wrap);

  let winner = null;
  const teamBtns = wrap.querySelectorAll('.team-btn');
  const submitBtn = wrap.querySelector('#submitPrediction');

  function checkReady() {
    const s1 = wrap.querySelector('#score1').value;
    const s2 = wrap.querySelector('#score2').value;
    submitBtn.disabled = !(winner && s1 !== '' && s2 !== '');
  }

  teamBtns.forEach((b) => b.addEventListener('click', () => {
    teamBtns.forEach((x) => x.classList.remove('selected'));
    b.classList.add('selected');
    winner = b.dataset.winner;
    checkReady();
  }));
  wrap.querySelector('#score1').addEventListener('input', checkReady);
  wrap.querySelector('#score2').addEventListener('input', checkReady);

  wrap.querySelector('#cancelSheet').addEventListener('click', () => wrap.remove());
  wrap.addEventListener('click', (e) => { if (e.target === wrap) wrap.remove(); });

  submitBtn.addEventListener('click', async () => {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Сохраняем…';
    try {
      await api('/predict', {
        method: 'POST',
        body: JSON.stringify({
          match_id: match.id,
          winner,
          score1: parseInt(wrap.querySelector('#score1').value, 10),
          score2: parseInt(wrap.querySelector('#score2').value, 10),
          mvp: wrap.querySelector('#mvpInput').value || '',
        }),
      });
      wrap.remove();
      showToast('✅ Предсказание сохранено!');
      renderPickem();
    } catch (e) {
      showToast('❌ ' + e.message);
      submitBtn.disabled = false;
      submitBtn.textContent = 'Сохранить предсказание';
    }
  });
}

// ---------------------------------------------------------------- daily
async function renderDaily() {
  content.innerHTML = `<div class="empty-state">Загрузка…</div>`;
  const data = await api('/daily');
  if (!data.task) {
    content.innerHTML = `<div class="empty-state"><span class="emoji">🌙</span>СЕГОДНЯ ЗАДАНИЙ НЕТ<br>Возвращайся завтра!</div>`;
    return;
  }
  content.innerHTML = `
    <div class="section-title">Ежедневное задание</div>
    <div class="daily-card">
      <div class="daily-desc">${escapeHtml(data.task.description)}</div>
      <div class="daily-points">+${data.task.points} PTS</div>
      <br>
      ${data.completed
        ? `<div style="margin-top:16px;color:var(--accent-green);font-weight:700;">✅ Уже выполнено</div>`
        : `<button class="btn-primary" id="completeTaskBtn">✅ Выполнить задание</button>`}
    </div>
  `;
  const btn = document.getElementById('completeTaskBtn');
  if (btn) {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        const r = await api('/daily/complete', { method: 'POST', body: JSON.stringify({ task_id: data.task.id }) });
        showToast(`✅ +${r.points} pts!`);
        const me = await api('/me');
        pointsValue.textContent = me.points;
        renderDaily();
      } catch (e) {
        showToast('❌ ' + e.message);
        btn.disabled = false;
      }
    });
  }
}

// ------------------------------------------------------------------ top
async function renderTop() {
  content.innerHTML = `<div class="empty-state">Загрузка…</div>`;
  const data = await api('/top');
  if (!data.top.length) {
    content.innerHTML = `<div class="empty-state">Пока никто не участвовал.</div>`;
    return;
  }
  const medalClass = ['gold', 'silver', 'bronze'];
  const rows = data.top.map((u, i) => `
    <div class="top-row ${medalClass[i] || ''}">
      <div class="top-rank">${i + 1}</div>
      <div class="top-avatar">${i < 3 ? ['🥇', '🥈', '🥉'][i] : '👤'}</div>
      <div class="top-info">
        <div class="top-name">${escapeHtml(u.username)}</div>
        <div class="top-sub">${u.correct}/${u.total} верных · ${u.accuracy}%</div>
      </div>
      <div class="top-points">${u.points}</div>
    </div>`).join('');
  content.innerHTML = `<div class="section-title">Топ игроков</div>${rows}`;
}

// ---------------------------------------------------------------- stats
async function renderStats() {
  content.innerHTML = `<div class="empty-state">Загрузка…</div>`;
  const [stats, me] = await Promise.all([api('/stats'), api('/me')]);
  pointsValue.textContent = me.points;

  const partnersHtml = me.channels.length ? `
    <div class="partners-card">
      <div class="partners-title">Наши партнёры</div>
      ${me.channels.map((ch) => `
        <div class="partner-row">
          <span>⭐ ${escapeHtml(ch.name)}</span>
          <span class="partner-status ${ch.subscribed ? 'ok' : 'no'}">${ch.subscribed ? '✓ Подписан' : '✕ Не подписан'}</span>
        </div>`).join('')}
      ${me.bonus_claimed ? `<div style="margin-top:10px;color:var(--accent-green);font-size:12px;font-weight:700;">✓ Бонус уже получен</div>` : ''}
    </div>` : '';

  content.innerHTML = `
    <div class="section-title">Ваша статистика</div>
    <div class="stats-grid">
      <div class="stat-box"><div class="stat-value yellow">${stats.points}</div><div class="stat-label">Очки</div></div>
      <div class="stat-box"><div class="stat-value green">${stats.accuracy}%</div><div class="stat-label">Точность</div></div>
      <div class="stat-box"><div class="stat-value blue">${stats.total}</div><div class="stat-label">Предсказаний</div></div>
      <div class="stat-box"><div class="stat-value">${stats.correct}</div><div class="stat-label">Верных</div></div>
    </div>
    ${partnersHtml}
  `;
}

// ---------------------------------------------------------------- admin
async function renderAdmin() {
  if (!state.isAdmin) { switchTab('pickem'); return; }
  content.innerHTML = `<div class="empty-state">Загрузка…</div>`;

  const [tRes, taskRes, chRes] = await Promise.all([
    api('/admin/tournaments'),
    api('/admin/daily-tasks'),
    api('/admin/channels'),
  ]);

  const tournamentsHtml = tRes.tournaments.map((t) => `
    <div class="admin-list-item">
      <span>#${t.id} ${escapeHtml(t.name)} — ${escapeHtml(t.stage)}</span>
      <span class="admin-badge">${t.status === 'active' ? '🟢 активен' : '⚪'}</span>
    </div>`).join('') || '<div class="admin-list-item">Турниров пока нет</div>';

  const tasksHtml = taskRes.tasks.map((t) => `
    <div class="admin-list-item">
      <span>[${t.task_date}] ${escapeHtml(t.description)} (+${t.points})</span>
      <span class="del" data-del-task="${t.id}">Удалить</span>
    </div>`).join('') || '<div class="admin-list-item">Заданий пока нет</div>';

  const channelsHtml = chRes.channels.map((c) => `
    <div class="admin-list-item">
      <span>${escapeHtml(c.display_name)} (${escapeHtml(c.chat_username)})</span>
      <span class="del" data-del-channel="${c.id}">Удалить</span>
    </div>`).join('') || '<div class="admin-list-item">Каналов пока нет</div>';

  content.innerHTML = `
    <div class="section-title">Админ-панель</div>

    <div class="admin-block">
      <div class="admin-block-title">➕ Новый турнир</div>
      <input class="text-input" id="tName" placeholder="Название турнира" style="margin-bottom:8px;">
      <input class="text-input" id="tStage" placeholder="Стадия (напр. Групповая стадия)" style="margin-bottom:8px;">
      <button class="btn-primary" id="addTournamentBtn">Создать и сделать активным</button>
      <div style="margin-top:14px;">${tournamentsHtml}</div>
    </div>

    <div class="admin-block">
      <div class="admin-block-title">➕ Новый матч (в активный турнир)</div>
      <input class="text-input" id="mTeam1" placeholder="Команда 1" style="margin-bottom:8px;">
      <input class="text-input" id="mTeam2" placeholder="Команда 2" style="margin-bottom:8px;">
      <input class="text-input" id="mTime" placeholder="Дата/время (необязательно)" style="margin-bottom:8px;">
      <button class="btn-primary" id="addMatchBtn">Добавить матч</button>
    </div>

    <div class="admin-block">
      <div class="admin-block-title">🏁 Внести результат матча</div>
      <select class="text-input" id="resultMatchSelect" style="margin-bottom:8px;"></select>
      <select class="text-input" id="resultWinnerSelect" style="margin-bottom:8px;"></select>
      <div class="score-row" style="margin-bottom:8px;">
        <input class="score-input" type="number" id="resultScore1" placeholder="0">
        <span class="score-sep">:</span>
        <input class="score-input" type="number" id="resultScore2" placeholder="0">
      </div>
      <input class="text-input" id="resultMvp" placeholder="MVP матча" style="margin-bottom:8px;">
      <button class="btn-primary" id="submitResultBtn">Сохранить результат</button>
    </div>

    <div class="admin-block">
      <div class="admin-block-title">⚡ Ежедневное задание (на сегодня)</div>
      <input class="text-input" id="taskDesc" placeholder="Текст задания" style="margin-bottom:8px;">
      <input class="text-input" id="taskPoints" type="number" placeholder="Очки за выполнение" style="margin-bottom:8px;">
      <button class="btn-primary" id="addTaskBtn">Добавить задание</button>
      <div style="margin-top:14px;">${tasksHtml}</div>
    </div>

    <div class="admin-block">
      <div class="admin-block-title">⭐ Партнёрский канал</div>
      <input class="text-input" id="chUsername" placeholder="@username канала" style="margin-bottom:8px;">
      <input class="text-input" id="chName" placeholder="Отображаемое имя" style="margin-bottom:8px;">
      <button class="btn-primary" id="addChannelBtn">Добавить канал</button>
      <div style="margin-top:14px;">${channelsHtml}</div>
    </div>
  `;

  // -- new tournament
  document.getElementById('addTournamentBtn').addEventListener('click', async () => {
    const name = document.getElementById('tName').value.trim();
    const stage = document.getElementById('tStage').value.trim() || 'Групповая стадия';
    if (!name) return showToast('Введите название турнира');
    await api('/admin/tournaments', { method: 'POST', body: JSON.stringify({ name, stage }) });
    showToast('✅ Турнир создан');
    renderAdmin();
  });

  // -- new match
  document.getElementById('addMatchBtn').addEventListener('click', async () => {
    const active = tRes.tournaments.find((t) => t.status === 'active');
    if (!active) return showToast('Сначала создайте турнир');
    const team1 = document.getElementById('mTeam1').value.trim();
    const team2 = document.getElementById('mTeam2').value.trim();
    const match_time = document.getElementById('mTime').value.trim() || null;
    if (!team1 || !team2) return showToast('Укажите обе команды');
    await api('/admin/matches', { method: 'POST', body: JSON.stringify({ tournament_id: active.id, team1, team2, match_time }) });
    showToast('✅ Матч добавлен');
    renderAdmin();
  });

  // -- result form: populate pending matches for active tournament
  const active = tRes.tournaments.find((t) => t.status === 'active');
  const matchSelect = document.getElementById('resultMatchSelect');
  const winnerSelect = document.getElementById('resultWinnerSelect');
  let pendingMatches = [];
  if (active) {
    const mRes = await api(`/admin/matches?tournament_id=${active.id}`);
    pendingMatches = mRes.matches.filter((m) => m.status === 'pending');
  }
  matchSelect.innerHTML = pendingMatches.length
    ? pendingMatches.map((m) => `<option value="${m.id}">${escapeHtml(m.team1)} vs ${escapeHtml(m.team2)}</option>`).join('')
    : `<option value="">Нет незавершённых матчей</option>`;

  function refreshWinnerOptions() {
    const m = pendingMatches.find((x) => String(x.id) === matchSelect.value);
    winnerSelect.innerHTML = m
      ? `<option value="${escapeHtml(m.team1)}">${escapeHtml(m.team1)}</option><option value="${escapeHtml(m.team2)}">${escapeHtml(m.team2)}</option>`
      : '';
  }
  matchSelect.addEventListener('change', refreshWinnerOptions);
  refreshWinnerOptions();

  document.getElementById('submitResultBtn').addEventListener('click', async () => {
    if (!matchSelect.value) return showToast('Нет доступных матчей');
    const score1 = parseInt(document.getElementById('resultScore1').value, 10);
    const score2 = parseInt(document.getElementById('resultScore2').value, 10);
    const mvp = document.getElementById('resultMvp').value.trim();
    if (Number.isNaN(score1) || Number.isNaN(score2)) return showToast('Укажите счёт');
    await api(`/admin/matches/${matchSelect.value}/result`, {
      method: 'POST',
      body: JSON.stringify({ winner: winnerSelect.value, score1, score2, mvp }),
    });
    showToast('✅ Результат сохранён, очки начислены');
    renderAdmin();
  });

  // -- new daily task
  document.getElementById('addTaskBtn').addEventListener('click', async () => {
    const description = document.getElementById('taskDesc').value.trim();
    const points = parseInt(document.getElementById('taskPoints').value, 10);
    if (!description || Number.isNaN(points)) return showToast('Заполните оба поля');
    await api('/admin/daily-tasks', { method: 'POST', body: JSON.stringify({ description, points }) });
    showToast('✅ Задание добавлено');
    renderAdmin();
  });

  content.querySelectorAll('[data-del-task]').forEach((el) => {
    el.addEventListener('click', async () => {
      await api(`/admin/daily-tasks/${el.dataset.delTask}`, { method: 'DELETE' });
      renderAdmin();
    });
  });

  // -- new channel
  document.getElementById('addChannelBtn').addEventListener('click', async () => {
    const chat_username = document.getElementById('chUsername').value.trim();
    const display_name = document.getElementById('chName').value.trim();
    if (!chat_username || !display_name) return showToast('Заполните оба поля');
    await api('/admin/channels', { method: 'POST', body: JSON.stringify({ chat_username, display_name }) });
    showToast('✅ Канал добавлен');
    renderAdmin();
  });

  content.querySelectorAll('[data-del-channel]').forEach((el) => {
    el.addEventListener('click', async () => {
      await api(`/admin/channels/${el.dataset.delChannel}`, { method: 'DELETE' });
      renderAdmin();
    });
  });
}

bootstrap();
