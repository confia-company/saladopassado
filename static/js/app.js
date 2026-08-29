const state = {
  user: null,
  tasks: [],
  essays: [],
  matificAssigned: [],
  matificAdventure: [],
  matificStats: null,
  currentTask: null,
  currentAnswers: {},
  isEssay: false,
  currentMatificEp: null,
  currentMatificJobId: null,
  matificJobPollInterval: null,
  matificBatchPollInterval: null,
};

const el = {
  viewAuth: document.getElementById('view-auth'),
  viewDashboard: document.getElementById('view-dashboard'),
  formLogin: document.getElementById('form-login'),
  btnLogin: document.getElementById('btn-login'),
  inputRa: document.getElementById('input-ra'),
  inputDigito: document.getElementById('input-digito'),
  inputUf: document.getElementById('input-uf'),
  inputPassword: document.getElementById('input-password'),
  btnTogglePassword: document.getElementById('btn-toggle-password'),
  inputSearchTasks: document.getElementById('input-search-tasks'),
  navName: document.getElementById('nav-name'),
  navRa: document.getElementById('nav-ra'),
  navAvatar: document.getElementById('nav-avatar'),
  btnLogout: document.getElementById('btn-logout'),
  btnRefreshTasks: document.getElementById('btn-refresh-tasks'),
  tasksGrid: document.getElementById('tasks-grid'),
  essaysGrid: document.getElementById('essays-grid'),
  badgeTasksCount: document.getElementById('badge-tasks-count'),
  badgeEssaysCount: document.getElementById('badge-essays-count'),
  badgeMatificCount: document.getElementById('badge-matific-count'),
  badgeMatificAssigned: document.getElementById('badge-matific-assigned'),
  badgeMatificAdventure: document.getElementById('badge-matific-adventure'),
  matificAssignedGrid: document.getElementById('matific-assigned-grid'),
  matificAdventureGrid: document.getElementById('matific-adventure-grid'),
  tabBtns: document.querySelectorAll('.tab-btn'),
  tabPanes: document.querySelectorAll('.tab-pane'),
  subnavPills: document.querySelectorAll('.subnav-pill'),
  matificSubpanes: document.querySelectorAll('.matific-subpane'),
  quickCoins: document.getElementById('quick-coins'),
  quickXp: document.getElementById('quick-xp'),
  quickRank: document.getElementById('quick-rank'),
  profileAvatarInitial: document.getElementById('profile-avatar-initial'),
  profileStudentName: document.getElementById('profile-student-name'),
  profileCoins: document.getElementById('profile-coins'),
  profileXp: document.getElementById('profile-xp'),
  profileRank: document.getElementById('profile-rank'),
  profileGoal: document.getElementById('profile-goal'),
  customizerSlotsGrid: document.getElementById('customizer-slots-grid'),
  btnRepairCustomization: document.getElementById('btn-repair-customization'),
  btnOpenSetStats: document.getElementById('btn-open-set-stats'),
  modalTask: document.getElementById('modal-task'),
  btnCloseModal: document.getElementById('btn-close-modal'),
  modalTaskTitle: document.getElementById('modal-task-title'),
  modalTaskBadge: document.getElementById('modal-task-badge'),
  taskLoading: document.getElementById('task-loading'),
  taskContent: document.getElementById('task-content'),
  taskDescription: document.getElementById('task-description'),
  questionsContainer: document.getElementById('questions-container'),
  essayEditorContainer: document.getElementById('essay-editor-container'),
  essayTitleInput: document.getElementById('essay-title-input'),
  essayBodyInput: document.getElementById('essay-body-input'),
  essayCharCounter: document.getElementById('essay-char-counter'),
  btnAiFill: document.getElementById('btn-ai-fill'),
  btnSubmitNow: document.getElementById('btn-submit-now'),
  btnSubmitDelayed: document.getElementById('btn-submit-delayed'),
  aiModelName: document.getElementById('ai-model-name'),
  modalMatificSim: document.getElementById('modal-matific-sim'),
  btnCloseMatificModal: document.getElementById('btn-close-matific-modal'),
  modalMatificTitle: document.getElementById('modal-matific-title'),
  simAccuracy: document.getElementById('sim-accuracy'),
  simSpeed: document.getElementById('sim-speed'),
  matificSimStatusText: document.getElementById('matific-sim-status-text'),
  matificSimPercent: document.getElementById('matific-sim-percent'),
  matificSimProgressFill: document.getElementById('matific-sim-progress-fill'),
  matificSimLogs: document.getElementById('matific-sim-logs'),
  btnStartMatificSim: document.getElementById('btn-start-matific-sim'),
  btnStopMatificSim: document.getElementById('btn-stop-matific-sim'),
  batchSourceSelect: document.getElementById('batch-source-select'),
  batchAccuracySelect: document.getElementById('batch-accuracy-select'),
  batchSpeedSelect: document.getElementById('batch-speed-select'),
  btnStartBatch: document.getElementById('btn-start-batch'),
  btnStopBatch: document.getElementById('btn-stop-batch'),
  batchStatusBadge: document.getElementById('batch-status-badge'),
  batchCurrentTitle: document.getElementById('batch-current-title'),
  batchProgressCounter: document.getElementById('batch-progress-counter'),
  batchProgressFill: document.getElementById('batch-progress-fill'),
  batchTerminalLogs: document.getElementById('batch-terminal-logs'),
  modalMatificStats: document.getElementById('modal-matific-stats'),
  btnCloseStatsModal: document.getElementById('btn-close-stats-modal'),
  btnSaveMatificStats: document.getElementById('btn-save-matific-stats'),
  inputEditCoins: document.getElementById('input-edit-coins'),
  inputEditXp: document.getElementById('input-edit-xp'),
  inputEditRank: document.getElementById('input-edit-rank'),
  toastContainer: document.getElementById('toast-container'),
};

const TOAST_ICONS = {
  success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--success);flex-shrink:0;"><polyline points="20 6 9 17 4 12"/></svg>',
  error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--danger);flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--warning);flex-shrink:0;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--primary);flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
};

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `${TOAST_ICONS[type] || TOAST_ICONS.info}<span>${message}</span>`;
  el.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function stripHtml(html) {
  if (!html) return '';
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

function formatDate(isoStr) {
  if (!isoStr) return 'Sem prazo';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return isoStr;
  }
}

function switchView(viewName) {
  if (viewName === 'auth') {
    el.viewAuth.classList.add('active');
    el.viewDashboard.classList.remove('active');
  } else {
    el.viewAuth.classList.remove('active');
    el.viewDashboard.classList.add('active');
  }
}

async function checkAuth() {
  try {
    const res = await fetch('/api/me');
    if (res.ok) {
      const data = await res.json();
      state.user = data;
      renderUserProfile();
      switchView('dashboard');
      loadAllData();
    } else {
      switchView('auth');
    }
  } catch {
    switchView('auth');
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const ra = el.inputRa.value.trim();
  const digito = el.inputDigito.value.trim();
  const uf = el.inputUf.value.trim().toUpperCase();
  const password = el.inputPassword.value;

  const btnText = el.btnLogin.querySelector('.btn-text');
  const spinner = el.btnLogin.querySelector('.spinner');
  btnText.textContent = 'Autenticando...';
  spinner.classList.remove('hidden');
  el.btnLogin.disabled = true;

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ra, digito, uf, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Erro ao efetuar login.');
    }

    state.user = data.user;
    renderUserProfile();
    showToast(`Bem-vindo, ${data.user.name.split(' ')[0]}!`, 'success');
    switchView('dashboard');
    loadAllData();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btnText.textContent = 'Entrar na Plataforma';
    spinner.classList.add('hidden');
    el.btnLogin.disabled = false;
  }
}

async function handleLogout() {
  fetch('/api/logout', { method: 'POST' }).catch(() => {});
  state.user = null;
  state.tasks = [];
  state.essays = [];
  state.matificAssigned = [];
  state.matificAdventure = [];
  state.matificStats = null;
  switchView('auth');
  showToast('Sessão encerrada.', 'info');
}

function renderUserProfile() {
  if (!state.user) return;
  el.navName.textContent = state.user.name;
  el.navRa.textContent = `RA: ${state.user.ra}-${state.user.digito} / ${state.user.uf}`;
  el.navAvatar.textContent = (state.user.name || 'A').charAt(0).toUpperCase();
  if (el.profileAvatarInitial) el.profileAvatarInitial.textContent = (state.user.name || 'A').charAt(0).toUpperCase();
  if (el.profileStudentName) el.profileStudentName.textContent = state.user.name;
}

let isMatificLoading = false;

function renderSkeletons(container, count = 4) {
  if (!container) return;
  container.innerHTML = Array(count).fill(0).map(() => '<div class="skeleton-card"></div>').join('');
}

function loadAllData() {
  if (el.badgeTasksCount) el.badgeTasksCount.innerHTML = '<span class="badge-loading">...</span>';
  if (el.badgeEssaysCount) el.badgeEssaysCount.innerHTML = '<span class="badge-loading">...</span>';
  if (el.badgeMatificCount) el.badgeMatificCount.innerHTML = '<span class="badge-loading">...</span>';
  if (el.badgeMatificAssigned) el.badgeMatificAssigned.innerHTML = '<span class="badge-loading">...</span>';
  if (el.badgeMatificAdventure) el.badgeMatificAdventure.innerHTML = '<span class="badge-loading">...</span>';

  loadTasks();
  loadMatificData();
}

async function loadTasks() {
  el.tasksGrid.innerHTML = '<div class="loading-state" style="grid-column:1/-1;"><div class="spinner"></div><p>Carregando tarefas...</p></div>';
  el.essaysGrid.innerHTML = '<div class="loading-state" style="grid-column:1/-1;"><div class="spinner"></div><p>Carregando redações...</p></div>';

  try {
    const res = await fetch('/api/tasks');
    if (!res.ok) throw new Error('Falha ao carregar lista de tarefas.');

    const data = await res.json();
    state.tasks = data.tasks || [];
    state.essays = data.essays || [];

    if (el.badgeTasksCount) el.badgeTasksCount.textContent = state.tasks.length;
    if (el.badgeEssaysCount) el.badgeEssaysCount.textContent = state.essays.length;

    renderFilteredTasks();
  } catch (err) {
    if (el.badgeTasksCount) el.badgeTasksCount.textContent = '0';
    if (el.badgeEssaysCount) el.badgeEssaysCount.textContent = '0';
    showToast(err.message, 'error');
  }
}

function renderFilteredTasks() {
  const query = el.inputSearchTasks ? el.inputSearchTasks.value.trim().toLowerCase() : '';
  
  const filteredTasks = state.tasks.filter(t => 
    (t.title || '').toLowerCase().includes(query) || 
    (t.description || '').toLowerCase().includes(query)
  );

  const filteredEssays = state.essays.filter(t => 
    (t.title || '').toLowerCase().includes(query) || 
    (t.description || '').toLowerCase().includes(query)
  );

  renderTaskGrid(el.tasksGrid, filteredTasks, false);
  renderTaskGrid(el.essaysGrid, filteredEssays, true);
  renderFilteredMatific();
}

function renderTaskGrid(container, items, isEssay) {
  if (items.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;text-align:center;padding:3rem 1rem;color:var(--text-secondary);">
        <p>Nenhuma atividade pendente encontrada.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="task-card glass-panel" data-id="${item.id}" data-essay="${isEssay}">
      <div class="task-card-header">
        <span class="badge ${isEssay ? 'badge-purple' : 'badge-indigo'}">${isEssay ? 'Redação' : 'Tarefa'}</span>
        <span class="task-date">${formatDate(item.expire_at || item.due_date)}</span>
      </div>
      <h3 class="task-title" title="${item.title}">${item.title}</h3>
      <p class="task-snippet">${stripHtml(item.description || 'Sem descrição informada.')}</p>
      <div class="task-footer">
        <span class="task-meta">${item.questions_count ? item.questions_count + ' questões' : ''}</span>
        <button class="btn btn-primary btn-sm btn-open-task" data-id="${item.id}" data-essay="${isEssay}">
          <span>Resolver com IA</span>
        </button>
      </div>
    </div>
  `).join('');

  container.querySelectorAll('.btn-open-task').forEach(btn => {
    btn.addEventListener('click', () => {
      const taskId = btn.dataset.id;
      const isEssayType = btn.dataset.essay === 'true';
      openTaskModal(taskId, isEssayType);
    });
  });
}

async function loadMatificData() {
  isMatificLoading = true;
  if (el.matificAssignedGrid) renderSkeletons(el.matificAssignedGrid, 4);
  if (el.matificAdventureGrid) renderSkeletons(el.matificAdventureGrid, 4);

  try {
    const [resAssigned, resAdv] = await Promise.allSettled([
      fetch('/api/matific/episodes?source=trabalho_atribuido'),
      fetch('/api/matific/episodes?source=ilha_aventura')
    ]);

    if (resAssigned.status === 'fulfilled' && resAssigned.value.ok) {
      const dataAssigned = await resAssigned.value.json();
      state.matificAssigned = dataAssigned.episodes || [];
    }

    if (resAdv.status === 'fulfilled' && resAdv.value.ok) {
      const dataAdv = await resAdv.value.json();
      state.matificAdventure = dataAdv.episodes || [];
    }

    loadMatificState();

    const uncompletedAssigned = state.matificAssigned.filter(e => !e.completed).length;
    const uncompletedAdv = state.matificAdventure.filter(e => !e.completed).length;
    if (el.badgeMatificAssigned) el.badgeMatificAssigned.textContent = uncompletedAssigned;
    if (el.badgeMatificAdventure) el.badgeMatificAdventure.textContent = uncompletedAdv;
    if (el.badgeMatificCount) el.badgeMatificCount.textContent = uncompletedAssigned + uncompletedAdv;

    renderFilteredMatific();
  } catch (err) {
    console.error('Matific load error', err);
  } finally {
    isMatificLoading = false;
  }
}

async function loadMatificState() {
  try {
    const res = await fetch('/api/matific/state');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.success || !data.state) return;
    state.matificStats = data.state;

    const s = state.matificStats;
    if (el.quickCoins) el.quickCoins.textContent = (s.coins || 0).toLocaleString('pt-BR');
    if (el.quickXp) el.quickXp.textContent = `${s.xp || 0} XP`;
    if (el.quickRank) el.quickRank.textContent = s.rank || 1;

    if (el.profileCoins) el.profileCoins.textContent = (s.coins || 0).toLocaleString('pt-BR');
    if (el.profileXp) el.profileXp.textContent = `${s.xp || 0} XP`;
    if (el.profileRank) el.profileRank.textContent = `Rank ${s.rank || 1}`;
    if (el.profileGoal) el.profileGoal.textContent = `${Math.round((s.weekly_goal || 0) / 60)} min / 30 min`;

    renderCustomizer();
  } catch (err) {
    console.error('Error loading matific state', err);
  }
}

function renderFilteredMatific() {
  const query = el.inputSearchTasks ? el.inputSearchTasks.value.trim().toLowerCase() : '';

  const filterEp = (ep) => (ep.title || '').toLowerCase().includes(query) || (ep.slug || '').toLowerCase().includes(query);

  const filteredAssigned = (state.matificAssigned || []).filter(filterEp);
  const filteredAdv = (state.matificAdventure || []).filter(filterEp);

  renderMatificGrid(el.matificAssignedGrid, filteredAssigned);
  renderMatificGrid(el.matificAdventureGrid, filteredAdv);
}

function renderMatificGrid(container, episodes) {
  if (!container) return;
  if (!episodes || episodes.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1;text-align:center;padding:3rem 1rem;color:var(--text-secondary);">
        <p>Nenhum episódio encontrado.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = episodes.map((ep, idx) => {
    const isDone = ep.completed || ep.was_passed;
    const badgeStatus = isDone 
      ? `<span class="badge badge-success">Concluído (${ep.highest_score || 6}/${ep.problem_count || 6})</span>`
      : `<span class="badge badge-cyan">Pendente</span>`;

    return `
      <div class="task-card glass-panel" data-index="${idx}">
        <div class="task-card-header">
          ${badgeStatus}
          <span class="task-date">${ep.source || 'Matific'}</span>
        </div>
        <h3 class="task-title" title="${ep.title}">${ep.title}</h3>
        <p class="task-snippet">${ep.subtitle || ep.slug || ''}</p>
        <div class="task-footer">
          <span class="task-meta">${ep.problem_count || 6} questões</span>
          <button class="btn btn-primary btn-sm btn-open-matific-sim" data-slug="${ep.slug}">
            <span>${isDone ? 'Refazer' : 'Simular Episódio'}</span>
          </button>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.btn-open-matific-sim').forEach(btn => {
    btn.addEventListener('click', () => {
      const slug = btn.dataset.slug;
      const all = [...state.matificAssigned, ...state.matificAdventure];
      const found = all.find(e => e.slug === slug);
      if (found) {
        openMatificSimModal(found);
      }
    });
  });
}

function renderCustomizer() {
  if (!el.customizerSlotsGrid || !state.matificStats) return;
  const s = state.matificStats;
  const inventory = s.inventory || [];
  const customization = s.customization || {};

  const SLOTS = [
    { key: "Head", label: "Cabelo / Cabeça", prefix: ["Body_Hair", "Outfit_Head"] },
    { key: "Face", label: "Rosto / Barba", prefix: ["Body_Mouth", "Body_Eyes", "Body_Ears", "Outfit_Face"] },
    { key: "Color", label: "Cor de Pele", prefix: ["Body_Color"] },
    { key: "Torso", label: "Tronco / Roupas", prefix: ["Outfit_Torso"] },
    { key: "Legs", label: "Pernas / Calças", prefix: ["Outfit_Legs"] },
    { key: "Hands", label: "Mãos / Luvas", prefix: ["Outfit_Hands"] },
    { key: "Feets", label: "Pés / Calçados", prefix: ["Outfit_Feets"] },
    { key: "Body", label: "Aeronave: Corpo", prefix: ["Aircraft_Body"] },
    { key: "Wings", label: "Aeronave: Asas", prefix: ["Aircraft_Wings"] },
    { key: "Wheels", label: "Aeronave: Rodas", prefix: ["Aircraft_Wheels"] },
    { key: "Balloon", label: "Aeronave: Balão", prefix: ["Aircraft_Balloon"] },
    { key: "Seat", label: "Aeronave: Assento", prefix: ["Aircraft_Seat"] },
  ];

  el.customizerSlotsGrid.innerHTML = SLOTS.map(slot => {
    const currentEquipped = customization[slot.key] || "";
    const matchingItems = inventory.filter(itemId => 
      slot.prefix.some(p => itemId.startsWith(p))
    );

    const optionsHtml = [
      `<option value="" ${!currentEquipped ? 'selected' : ''}>Padrão / Desequipado</option>`,
      ...matchingItems.map(item => `
        <option value="${item}" ${currentEquipped === item ? 'selected' : ''}>
          ${item.replace(/^Aircraft_|^Outfit_|^Body_/, '').replace(/_/g, ' ')}
        </option>
      `)
    ].join('');

    return `
      <div class="slot-card glass-panel">
        <div class="slot-header">
          <span class="slot-label">${slot.label}</span>
          <span class="slot-equipped-badge">${currentEquipped ? 'Equipado' : 'Padrão'}</span>
        </div>
        <select class="slot-select" data-slot="${slot.key}">
          ${optionsHtml}
        </select>
      </div>
    `;
  }).join('');

  el.customizerSlotsGrid.querySelectorAll('.slot-select').forEach(sel => {
    sel.addEventListener('change', async () => {
      const partName = sel.dataset.slot;
      const itemId = sel.value;
      await handleEquipItem(partName, itemId);
    });
  });
}

async function handleEquipItem(partName, itemId) {
  if (!state.matificStats) return;
  try {
    const res = await fetch('/api/matific/equip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaign_id: state.matificStats.campaign_id,
        part_name: partName,
        item_id: itemId
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha ao equipar item.');
    showToast(`Item para ${partName} equipado com sucesso!`, 'success');
    loadMatificState();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleRepairCustomization() {
  if (!state.matificStats) return;
  try {
    const res = await fetch('/api/matific/repair-customization', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ campaign_id: state.matificStats.campaign_id })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao reparar customização.');
    if (data.repaired && data.repaired.length > 0) {
      showToast(`Chaves reparadas: ${data.repaired.join(', ')}`, 'success');
    } else {
      showToast('Nenhuma chave corrompida encontrada. O perfil está 100% íntegro.', 'info');
    }
    loadMatificState();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleSaveMatificStats() {
  if (!state.matificStats) return;
  const coins = parseInt(el.inputEditCoins.value, 10);
  const xp = parseInt(el.inputEditXp.value, 10);
  const rank = parseInt(el.inputEditRank.value, 10);

  try {
    const res = await fetch('/api/matific/set_stats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaign_id: state.matificStats.campaign_id,
        coins: isNaN(coins) ? null : coins,
        xp: isNaN(xp) ? null : xp,
        rank: isNaN(rank) ? null : rank
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao atualizar estatísticas.');
    showToast('Estatísticas atualizadas com sucesso!', 'success');
    el.modalMatificStats.classList.add('hidden');
    loadMatificState();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openMatificSimModal(ep) {
  state.currentMatificEp = ep;
  el.modalMatificTitle.textContent = ep.title || ep.slug;
  el.matificSimStatusText.textContent = 'Pronto para iniciar';
  el.matificSimPercent.textContent = '0%';
  el.matificSimProgressFill.style.width = '0%';
  el.matificSimLogs.innerHTML = '<div class="log-line text-muted">Aguardando comando de início...</div>';
  el.btnStartMatificSim.classList.remove('hidden');
  el.btnStopMatificSim.classList.add('hidden');
  el.modalMatificSim.classList.remove('hidden');
}

async function startMatificSimulation() {
  if (!state.currentMatificEp) return;
  const accuracy = el.simAccuracy.value;
  const speed = el.simSpeed.value;

  const timings = speed === 'fast' ? {
    reading_min: 0.5, reading_max: 1.5,
    solving_min: 1.5, solving_max: 3.5,
    struggle_min: 1.5, struggle_max: 3.0,
    inter_question_min: 0.3, inter_question_max: 0.8,
    loading_multiplier: 0.5
  } : {
    reading_min: 3.0, reading_max: 6.0,
    solving_min: 12.0, solving_max: 25.0,
    struggle_min: 8.0, struggle_max: 15.0,
    inter_question_min: 1.0, inter_question_max: 2.5,
    loading_multiplier: 1.0
  };

  el.btnStartMatificSim.classList.add('hidden');
  el.btnStopMatificSim.classList.remove('hidden');
  el.matificSimStatusText.textContent = 'Iniciando simulação...';

  try {
    const res = await fetch('/api/matific/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        episode: state.currentMatificEp,
        target_accuracy: accuracy,
        timings: timings
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha ao iniciar simulação.');

    state.currentMatificJobId = data.job_id;
    startMatificJobPolling(data.job_id);
  } catch (err) {
    showToast(err.message, 'error');
    el.btnStartMatificSim.classList.remove('hidden');
    el.btnStopMatificSim.classList.add('hidden');
  }
}

function startMatificJobPolling(jobId) {
  if (state.matificJobPollInterval) clearInterval(state.matificJobPollInterval);

  state.matificJobPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/matific/job/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();

      const pct = Math.round(job.progress_percent || 0);
      el.matificSimPercent.textContent = `${pct}%`;
      el.matificSimProgressFill.style.width = `${pct}%`;

      if (job.logs && job.logs.length > 0) {
        el.matificSimLogs.innerHTML = job.logs.map(l => `<div class="log-line">${l}</div>`).join('');
        el.matificSimLogs.scrollTop = el.matificSimLogs.scrollHeight;
        el.matificSimStatusText.textContent = job.logs[job.logs.length - 1];
      }

      if (job.status === 'completed') {
        clearInterval(state.matificJobPollInterval);
        showToast('Episódio concluído e pontuado com sucesso!', 'success');
        el.btnStartMatificSim.classList.remove('hidden');
        el.btnStopMatificSim.classList.add('hidden');
        loadMatificData();
      } else if (job.status === 'failed' || job.status === 'stopped') {
        clearInterval(state.matificJobPollInterval);
        showToast(job.status === 'stopped' ? 'Simulação interrompida.' : 'Simulação falhou.', 'warning');
        el.btnStartMatificSim.classList.remove('hidden');
        el.btnStopMatificSim.classList.add('hidden');
      }
    } catch (err) {
      console.error(err);
    }
  }, 1000);
}

async function stopMatificSimulation() {
  if (!state.currentMatificJobId) return;
  try {
    await fetch(`/api/matific/job/${state.currentMatificJobId}/stop`, { method: 'POST' });
    showToast('Comando de parada enviado.', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function startMatificBatch() {
  const source = el.batchSourceSelect.value;
  let targetEpisodes = [];

  if (source === 'assigned') {
    targetEpisodes = state.matificAssigned.filter(e => !e.completed && !e.was_passed);
  } else if (source === 'adventure') {
    targetEpisodes = state.matificAdventure.filter(e => !e.completed && !e.was_passed);
  } else {
    targetEpisodes = [
      ...state.matificAssigned.filter(e => !e.completed && !e.was_passed),
      ...state.matificAdventure.filter(e => !e.completed && !e.was_passed)
    ];
  }

  if (targetEpisodes.length === 0) {
    showToast('Nenhum episódio pendente para processamento.', 'info');
    return;
  }

  const accuracy = el.batchAccuracySelect.value;
  const speed = el.batchSpeedSelect.value;

  const minTime = speed === 'fast' ? 0.5 : 2.0;
  const maxTime = speed === 'fast' ? 1.5 : 4.0;
  const minWait = speed === 'fast' ? 0.2 : 0.5;
  const maxWait = speed === 'fast' ? 0.5 : 1.5;

  el.btnStartBatch.classList.add('hidden');
  el.btnStopBatch.classList.remove('hidden');
  el.batchStatusBadge.textContent = 'Executando';
  el.batchStatusBadge.className = 'badge badge-primary';
  el.batchTerminalLogs.innerHTML = '';

  try {
    const res = await fetch('/api/matific/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        episodes: targetEpisodes,
        target_accuracy: accuracy,
        min_time_per_task: minTime,
        max_time_per_task: maxTime,
        min_wait_between: minWait,
        max_wait_between: maxWait
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao iniciar lote.');

    state.currentMatificBatchId = data.batch_id;
    pollMatificBatch(data.batch_id);
  } catch (err) {
    showToast(err.message, 'error');
    el.btnStartBatch.classList.remove('hidden');
    el.btnStopBatch.classList.add('hidden');
    el.batchStatusBadge.textContent = 'Erro';
    el.batchStatusBadge.className = 'badge badge-danger';
  }
}

async function pollMatificBatch(batchId) {
  if (state.matificBatchPollInterval) clearInterval(state.matificBatchPollInterval);

  state.matificBatchPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/matific/batch/${batchId}`);
      if (!res.ok) return;
      const b = await res.json();

      el.batchProgressCounter.textContent = `${b.completed_count} / ${b.total_count}`;
      const pct = b.total_count > 0 ? (b.completed_count / b.total_count) * 100 : 0;
      el.batchProgressFill.style.width = `${pct}%`;

      if (b.current_episode) {
        el.batchCurrentTitle.textContent = `Executando: ${b.current_episode.title || b.current_episode.slug}`;
      } else {
        el.batchCurrentTitle.textContent = b.status === 'completed' ? 'Lote concluído!' : 'Aguardando...';
      }

      if (b.logs && b.logs.length > 0) {
        el.batchTerminalLogs.innerHTML = b.logs.map(l => `<div class="log-line">${l}</div>`).join('');
        el.batchTerminalLogs.scrollTop = el.batchTerminalLogs.scrollHeight;
      }

      if (['completed', 'stopped', 'failed'].includes(b.status)) {
        clearInterval(state.matificBatchPollInterval);
        state.matificBatchPollInterval = null;
        el.btnStartBatch.classList.remove('hidden');
        el.btnStopBatch.classList.add('hidden');
        el.batchStatusBadge.textContent = b.status === 'completed' ? 'Concluído' : (b.status === 'stopped' ? 'Parado' : 'Falha');
        el.batchStatusBadge.className = b.status === 'completed' ? 'badge badge-success' : 'badge badge-danger';
        showToast(`Lote finalizado com status: ${b.status}`, b.status === 'completed' ? 'success' : 'info');
        loadMatificData();
      }
    } catch (err) {
      console.error('Batch polling error', err);
    }
  }, 1000);
}

async function stopMatificBatch() {
  try {
    await fetch('/api/matific/batch/stop', { method: 'POST' });
    showToast('Lote interrompido pelo usuário.', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openTaskModal(taskId, isEssay) {
  state.isEssay = isEssay;
  state.currentTask = null;
  state.currentAnswers = {};

  el.modalTask.classList.remove('hidden');
  el.taskLoading.classList.remove('hidden');
  el.taskContent.classList.add('hidden');

  el.modalTaskBadge.textContent = isEssay ? 'Redação' : 'Tarefa';
  el.modalTaskBadge.className = isEssay ? 'badge badge-purple' : 'badge badge-indigo';
  el.modalTaskTitle.textContent = 'Carregando...';

  try {
    const res = await fetch(`/api/task/${taskId}`);
    if (!res.ok) throw new Error('Erro ao carregar conteúdo da tarefa.');

    const data = await res.json();
    state.currentTask = data;

    el.modalTaskTitle.textContent = data.title || 'Atividade';
    el.taskDescription.innerHTML = data.description ? `<p>${stripHtml(data.description)}</p>` : '';

    if (isEssay) {
      el.questionsContainer.classList.add('hidden');
      el.essayEditorContainer.classList.remove('hidden');
      el.essayTitleInput.value = '';
      el.essayBodyInput.value = '';
      updateEssayCharCount();
    } else {
      el.questionsContainer.classList.remove('hidden');
      el.essayEditorContainer.classList.add('hidden');
      renderQuestions(data.questions || []);
    }

    el.taskLoading.classList.add('hidden');
    el.taskContent.classList.remove('hidden');
  } catch (err) {
    showToast(err.message, 'error');
    closeModal();
  }
}

function getNormalizedOptions(q) {
  if (!q) return [];
  const opts = q.options;
  if (!opts) return [];

  if (Array.isArray(opts)) {
    return opts.map((opt, idx) => {
      let text = '';
      if (typeof opt === 'object' && opt !== null) {
        text = opt.text || opt.statement || opt.label || JSON.stringify(opt);
      } else {
        text = String(opt);
      }
      return { key: String(idx), text: stripHtml(text) };
    });
  }

  if (typeof opts === 'object') {
    if (Array.isArray(opts.words)) {
      return opts.words.map((w, idx) => ({ key: String(idx), text: stripHtml(String(w)) }));
    }
    if (Array.isArray(opts.items)) {
      return opts.items.map((it, idx) => ({ key: String(idx), text: stripHtml(String(it)) }));
    }
    if (opts.letters) {
      return [{ key: '0', text: `Preenchimento de letras (${opts.letters} letras)` }];
    }
    return Object.entries(opts).map(([k, v]) => {
      let text = '';
      if (typeof v === 'object' && v !== null) {
        text = v.text || v.statement || v.label || JSON.stringify(v);
      } else {
        text = String(v);
      }
      return { key: String(k), text: stripHtml(text) };
    });
  }

  return [];
}

function renderQuestions(questions) {
  if (!questions || questions.length === 0) {
    el.questionsContainer.innerHTML = '<div class="empty-state"><p>Nenhuma questão encontrada nesta atividade.</p></div>';
    return;
  }

  el.questionsContainer.innerHTML = questions.map((q, idx) => {
    const qType = q.type || 'múltipla escolha';
    if (qType === 'info' || qType === 'section') {
      return `
        <div class="question-block info-banner glass-panel" id="question-${q.id}">
          <div class="question-statement">${q.statement || q.text || ''}</div>
        </div>
      `;
    }

    const normalizedOptions = getNormalizedOptions(q);

    return `
      <div class="question-block glass-panel" id="question-${q.id}">
        <div class="question-header">
          <span class="question-number">Questão ${idx + 1}</span>
          <span class="badge badge-neutral">${qType}</span>
        </div>
        <div class="question-statement">${q.statement || ''}</div>
        <div class="options-container" id="options-${q.id}">
          ${normalizedOptions.map(opt => `
            <label class="option-row" data-qid="${q.id}" data-idx="${opt.key}">
              <input type="${qType === 'multi' ? 'checkbox' : 'radio'}" name="q-${q.id}" value="${opt.key}">
              <span class="option-text">${opt.text}</span>
            </label>
          `).join('')}
        </div>
      </div>
    `;
  }).join('');
}

function updateEssayCharCount() {
  const len = el.essayBodyInput.value.length;
  el.essayCharCounter.textContent = `${len} caracteres`;
}

async function handleAiFill() {
  if (!state.currentTask) return;
  const taskId = state.currentTask.id;

  const btnText = el.btnAiFill.querySelector('span');
  btnText.textContent = 'Resolvendo com IA...';
  el.btnAiFill.disabled = true;

  try {
    const res = await fetch(`/api/ai-fill/${taskId}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao processar resposta com IA.');

    state.currentAnswers = data.answers || {};

    if (state.isEssay) {
      const essayQ = (state.currentTask.questions || []).find(q => q.type === 'essay');
      const qid = String(essayQ?.id);
      const essayAns = state.currentAnswers[qid]?.answer;
      if (essayAns) {
        el.essayTitleInput.value = essayAns.title || '';
        el.essayBodyInput.value = essayAns.body || '';
        updateEssayCharCount();
      }
    } else {
      for (const [qid, ansData] of Object.entries(state.currentAnswers)) {
        const qElem = document.getElementById(`question-${qid}`);
        if (!qElem) continue;
        const ans = ansData.answer;
        if (typeof ans === 'object' && ans !== null && !Array.isArray(ans)) {
          for (const [optIdx, isSelected] of Object.entries(ans)) {
            if (isSelected === true || String(isSelected).toLowerCase() === 'true') {
              const optRow = qElem.querySelector(`.option-row[data-idx="${optIdx}"] input`);
              if (optRow) optRow.checked = true;
            }
          }
        } else if (typeof ans === 'string' || typeof ans === 'number') {
          const optRow = qElem.querySelector(`.option-row[data-idx="${ans}"] input`);
          if (optRow) optRow.checked = true;
        }
      }
    }

    showToast('Respostas geradas pela IA!', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btnText.textContent = 'Resolver com IA';
    el.btnAiFill.disabled = false;
  }
}

async function handleSubmit(delayed = false) {
  if (!state.currentTask) return;
  const taskId = state.currentTask.id;

  let payloadAnswers = state.currentAnswers;
  if (state.isEssay) {
    const essayQ = (state.currentTask.questions || []).find(q => q.type === 'essay');
    const qid = String(essayQ?.id);
    payloadAnswers = {
      [qid]: {
        question_id: essayQ?.id,
        question_type: 'essay',
        answer: {
          title: el.essayTitleInput.value.trim(),
          body: el.essayBodyInput.value.trim()
        }
      }
    };
  }

  if (Object.keys(payloadAnswers).length === 0) {
    showToast('Por favor, resolva a tarefa com IA antes de enviar.', 'warning');
    return;
  }

  const endpoint = delayed ? `/api/task/${taskId}/submit-delayed` : `/api/task/${taskId}/submit`;
  const btn = delayed ? el.btnSubmitDelayed : el.btnSubmitNow;
  btn.disabled = true;

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: payloadAnswers })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao enviar tarefa.');

    showToast(data.message || 'Tarefa enviada com sucesso!', 'success');
    closeModal();
    loadTasks();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

function closeModal() {
  el.modalTask.classList.add('hidden');
}

function closeMatificModal() {
  el.modalMatificSim.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  checkAuth();

  el.formLogin.addEventListener('submit', handleLogin);
  el.btnLogout.addEventListener('click', handleLogout);
  el.btnRefreshTasks.addEventListener('click', loadAllData);
  el.btnCloseModal.addEventListener('click', closeModal);
  el.btnAiFill.addEventListener('click', handleAiFill);
  el.btnSubmitNow.addEventListener('click', () => handleSubmit(false));
  el.btnSubmitDelayed.addEventListener('click', () => handleSubmit(true));

  if (el.btnCloseMatificModal) el.btnCloseMatificModal.addEventListener('click', closeMatificModal);
  if (el.btnStartMatificSim) el.btnStartMatificSim.addEventListener('click', startMatificSimulation);
  if (el.btnStopMatificSim) el.btnStopMatificSim.addEventListener('click', stopMatificSimulation);
  if (el.btnStartBatch) el.btnStartBatch.addEventListener('click', startMatificBatch);
  if (el.btnStopBatch) el.btnStopBatch.addEventListener('click', stopMatificBatch);
  if (el.btnRepairCustomization) el.btnRepairCustomization.addEventListener('click', handleRepairCustomization);
  if (el.btnOpenSetStats) {
    el.btnOpenSetStats.addEventListener('click', () => {
      if (state.matificStats) {
        el.inputEditCoins.value = state.matificStats.coins || 0;
        el.inputEditXp.value = state.matificStats.xp || 0;
        el.inputEditRank.value = state.matificStats.rank || 1;
      }
      el.modalMatificStats.classList.remove('hidden');
    });
  }
  if (el.btnCloseStatsModal) el.btnCloseStatsModal.addEventListener('click', () => el.modalMatificStats.classList.add('hidden'));
  if (el.btnSaveMatificStats) el.btnSaveMatificStats.addEventListener('click', handleSaveMatificStats);

  el.subnavPills.forEach(pill => {
    pill.addEventListener('click', () => {
      el.subnavPills.forEach(p => p.classList.remove('active'));
      el.matificSubpanes.forEach(pane => pane.classList.remove('active'));
      pill.classList.add('active');
      const subpaneId = `matific-subpane-${pill.dataset.subtab}`;
      const targetPane = document.getElementById(subpaneId);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  if (el.btnTogglePassword && el.inputPassword) {
    el.btnTogglePassword.addEventListener('click', () => {
      const isPwd = el.inputPassword.getAttribute('type') === 'password';
      el.inputPassword.setAttribute('type', isPwd ? 'text' : 'password');
      el.btnTogglePassword.style.color = isPwd ? 'var(--primary)' : 'var(--text-muted)';
    });
  }

  if (el.inputSearchTasks) {
    el.inputSearchTasks.addEventListener('input', renderFilteredTasks);
  }

  if (el.essayBodyInput) {
    el.essayBodyInput.addEventListener('input', updateEssayCharCount);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!el.modalTask.classList.contains('hidden')) closeModal();
      if (!el.modalMatificSim.classList.contains('hidden')) closeMatificModal();
      if (el.modalMatificStats && !el.modalMatificStats.classList.contains('hidden')) el.modalMatificStats.classList.add('hidden');
    }
  });

  el.tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      el.tabBtns.forEach(b => b.classList.remove('active'));
      el.tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = document.getElementById(btn.dataset.tab);
      if (pane) pane.classList.add('active');
    });
  });
});
