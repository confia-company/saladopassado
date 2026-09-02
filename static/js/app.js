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
  leiaspBooks: [],
  currentLeiaSPJobId: null,
  activeLeiaSPJob: null,
  leiaspJobPollInterval: null,
  selectedLeiaSPBook: null,
  isSequentialLeiaSP: false,
  selectedTaskIds: new Set(),
  activeTaskBatch: null,
  taskBatchPollInterval: null,
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
  badgeLeiaSPCount: document.getElementById('badge-leiasp-count'),
  leiaspGrid: document.getElementById('leiasp-grid'),
  leiaspStatTotal: document.getElementById('leiasp-stat-total'),
  leiaspStatCompleted: document.getElementById('leiasp-stat-completed'),
  leiaspStatPending: document.getElementById('leiasp-stat-pending'),
  btnRefreshLeiaSP: document.getElementById('btn-refresh-leiasp'),
  btnLeiaSPSeq: document.getElementById('btn-leiasp-seq'),
  modalLeiaSPReader: document.getElementById('modal-leiasp-reader'),
  leiaspModalTitle: document.getElementById('leiasp-modal-title'),
  btnCloseLeiaSPModal: document.getElementById('btn-close-leiasp-modal'),
  leiaspBookNameInput: document.getElementById('leiasp-book-name-input'),
  leiaspMinTime: document.getElementById('leiasp-min-time'),
  leiaspMaxTime: document.getElementById('leiasp-max-time'),
  leiaspAutoQuiz: document.getElementById('leiasp-auto-quiz'),
  btnStartLeiaSPRead: document.getElementById('btn-start-leiasp-read'),
  btnStopLeiaSPRead: document.getElementById('btn-stop-leiasp-read'),
  btnModalPauseResume: document.getElementById('btn-modal-pause-resume'),
  iconModalPause: document.getElementById('icon-modal-pause'),
  btnModalPauseText: document.getElementById('btn-modal-pause-text'),
  btnModalMinimize: document.getElementById('btn-modal-minimize'),
  leiaspConfigView: document.getElementById('leiasp-config-view'),
  leiaspProgressView: document.getElementById('leiasp-progress-view'),
  leiaspJobStatusText: document.getElementById('leiasp-job-status-text'),
  leiaspJobPercent: document.getElementById('leiasp-job-percent'),
  leiaspProgressBar: document.getElementById('leiasp-progress-bar'),
  leiaspPageCounter: document.getElementById('leiasp-page-counter'),
  leiaspJobState: document.getElementById('leiasp-job-state'),
  leiaspLogsBox: document.getElementById('leiasp-logs-box'),
  leiaspActiveBanner: document.getElementById('leiasp-active-banner'),
  activeBannerCover: document.getElementById('active-banner-cover'),
  activeBannerCoverFallback: document.getElementById('active-banner-cover-fallback'),
  activeBannerDot: document.getElementById('active-banner-dot'),
  activeBannerStatus: document.getElementById('active-banner-status'),
  activeBannerQueueBadge: document.getElementById('active-banner-queue-badge'),
  activeBannerTitle: document.getElementById('active-banner-title'),
  activeBannerProgressBar: document.getElementById('active-banner-progress-bar'),
  activeBannerPercent: document.getElementById('active-banner-percent'),
  activeBannerPage: document.getElementById('active-banner-page'),
  activeBannerLastLog: document.getElementById('active-banner-last-log'),
  btnBannerPauseResume: document.getElementById('btn-banner-pause-resume'),
  iconBannerPause: document.getElementById('icon-banner-pause'),
  btnBannerPauseText: document.getElementById('btn-banner-pause-text'),
  btnBannerStop: document.getElementById('btn-banner-stop'),
  btnBannerOpenModal: document.getElementById('btn-banner-open-modal'),
  tasksSelectAll: document.getElementById('tasks-select-all'),
  tasksSelectedCount: document.getElementById('tasks-selected-count'),
  btnBatchSolveTasks: document.getElementById('btn-batch-solve-tasks'),
  tasksBatchBanner: document.getElementById('tasks-batch-banner'),
  tasksBatchTitle: document.getElementById('tasks-batch-title'),
  tasksBatchStatusBadge: document.getElementById('tasks-batch-status-badge'),
  tasksBatchProgressBar: document.getElementById('tasks-batch-progress-bar'),
  tasksBatchCounter: document.getElementById('tasks-batch-counter'),
  tasksBatchActiveThreads: document.getElementById('tasks-batch-active-threads'),
  btnTasksBatchStop: document.getElementById('btn-tasks-batch-stop'),
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
  state.leiaspBooks = [];
  if (state.leiaspJobPollInterval) {
    clearInterval(state.leiaspJobPollInterval);
    state.leiaspJobPollInterval = null;
  }
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
  if (el.badgeLeiaSPCount) el.badgeLeiaSPCount.innerHTML = '<span class="badge-loading">...</span>';

  loadTasks();
  loadMatificData();
  loadLeiaSPData();
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
    checkActiveTasksBatch();
  } catch (err) {
    if (el.badgeTasksCount) el.badgeTasksCount.textContent = '0';
    if (el.badgeEssaysCount) el.badgeEssaysCount.textContent = '0';
    showToast(err.message, 'error');
  }
}

function updateTasksSelectionUI() {
  const count = state.selectedTaskIds.size;
  if (el.tasksSelectedCount) el.tasksSelectedCount.textContent = `${count} selecionada(s)`;
  if (el.btnBatchSolveTasks) el.btnBatchSolveTasks.classList.toggle('hidden', count === 0);
  if (el.tasksSelectAll) {
    const totalSelectable = state.tasks.length;
    el.tasksSelectAll.checked = totalSelectable > 0 && count === totalSelectable;
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
  updateTasksSelectionUI();
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

  container.innerHTML = items.map(item => {
    const isSelected = state.selectedTaskIds.has(item.id);
    const batchInfo = state.activeTaskBatch && state.activeTaskBatch.tasks ? state.activeTaskBatch.tasks[item.id] : null;
    let batchBadge = '';
    if (batchInfo) {
      if (batchInfo.status === 'resolving_ai') batchBadge = '<span class="badge badge-warning task-batch-live-badge">IA Resolvendo...</span>';
      else if (batchInfo.status === 'waiting_delay') batchBadge = `<span class="badge badge-indigo task-batch-live-badge">Delay (${batchInfo.remaining_seconds}s)</span>`;
      else if (batchInfo.status === 'submitting') batchBadge = '<span class="badge badge-warning task-batch-live-badge">Enviando...</span>';
      else if (batchInfo.status === 'completed') batchBadge = `<span class="badge badge-success task-batch-live-badge">${batchInfo.score !== null && batchInfo.score !== undefined ? 'Nota ' + batchInfo.score : 'Concluído'}</span>`;
      else if (batchInfo.status === 'failed') batchBadge = '<span class="badge badge-danger task-batch-live-badge">Falhou</span>';
      else if (batchInfo.status === 'stopped') batchBadge = '<span class="badge badge-danger task-batch-live-badge">Interrompido</span>';
    }

    return `
      <div class="task-card glass-panel ${isSelected ? 'task-selected' : ''}" data-id="${item.id}" data-essay="${isEssay}">
        <div class="task-card-header">
          <div class="task-card-header-left">
            ${!isEssay ? `<input type="checkbox" class="task-select-checkbox" data-id="${item.id}" ${isSelected ? 'checked' : ''}>` : ''}
            <span class="badge ${isEssay ? 'badge-purple' : 'badge-indigo'}">${isEssay ? 'Redação' : 'Tarefa'}</span>
          </div>
          <div class="task-card-header-right">
            ${batchBadge}
            <span class="task-date">${formatDate(item.expire_at || item.due_date)}</span>
          </div>
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
    `;
  }).join('');

  container.querySelectorAll('.btn-open-task').forEach(btn => {
    btn.addEventListener('click', () => {
      const taskId = btn.dataset.id;
      const isEssayType = btn.dataset.essay === 'true';
      openTaskModal(taskId, isEssayType);
    });
  });

  if (!isEssay) {
    container.querySelectorAll('.task-select-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        e.stopPropagation();
        const id = parseInt(cb.dataset.id);
        if (cb.checked) {
          state.selectedTaskIds.add(id);
        } else {
          state.selectedTaskIds.delete(id);
        }
        const card = cb.closest('.task-card');
        if (card) card.classList.toggle('task-selected', cb.checked);
        updateTasksSelectionUI();
      });
    });
  }
}

async function startTasksBatchSolve() {
  if (state.selectedTaskIds.size === 0) {
    showToast('Selecione pelo menos uma tarefa para executar em lote.', 'warning');
    return;
  }

  const taskIds = Array.from(state.selectedTaskIds);
  if (el.btnBatchSolveTasks) el.btnBatchSolveTasks.disabled = true;

  try {
    const res = await fetch('/api/tasks/batch-solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_ids: taskIds })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha ao iniciar execução em lote.');

    showToast(data.message || 'Tarefas iniciadas em paralelo com delay humanizado!', 'success');
    state.selectedTaskIds.clear();
    updateTasksSelectionUI();
    renderFilteredTasks();

    pollTasksBatch(data.batch_id);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (el.btnBatchSolveTasks) el.btnBatchSolveTasks.disabled = false;
  }
}

function pollTasksBatch(batchId) {
  if (state.taskBatchPollInterval) {
    clearInterval(state.taskBatchPollInterval);
  }

  state.taskBatchPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/tasks/batch/${batchId}`);
      if (!res.ok) {
        clearInterval(state.taskBatchPollInterval);
        state.taskBatchPollInterval = null;
        return;
      }

      const data = await res.json();
      const batch = data.batch;
      if (!batch) return;

      state.activeTaskBatch = batch;
      renderActiveTasksBatchBanner(batch);
      updateTaskCardBadges(batch);

      if (batch.status === 'completed' || batch.status === 'stopped' || batch.status === 'failed') {
        clearInterval(state.taskBatchPollInterval);
        state.taskBatchPollInterval = null;

        if (batch.status === 'completed') {
          showToast('Todas as tarefas do lote foram concluídas com sucesso!', 'success');
        } else if (batch.status === 'stopped') {
          showToast('Execução do lote de tarefas interrompida.', 'info');
        }

        setTimeout(() => {
          if (el.tasksBatchBanner) el.tasksBatchBanner.classList.add('hidden');
          loadTasks();
        }, 3500);
      }
    } catch (err) {}
  }, 1000);
}

function renderActiveTasksBatchBanner(batch) {
  if (!el.tasksBatchBanner || !batch) return;
  el.tasksBatchBanner.classList.remove('hidden');

  const total = batch.total || 0;
  const completed = batch.completed_count || 0;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  const runningCount = Object.values(batch.tasks || {}).filter(t => t.status === 'resolving_ai' || t.status === 'waiting_delay' || t.status === 'submitting').length;

  if (el.tasksBatchTitle) el.tasksBatchTitle.textContent = `Executando ${total} Tarefas em Paralelo (${runningCount} threads ativas)`;
  if (el.tasksBatchProgressBar) el.tasksBatchProgressBar.style.width = `${percent}%`;
  if (el.tasksBatchCounter) el.tasksBatchCounter.textContent = `${completed} / ${total} concluídas (${percent}%)`;
  if (el.tasksBatchActiveThreads) el.tasksBatchActiveThreads.textContent = `${runningCount} em processamento`;

  const isStopped = batch.status === 'stopped';
  const isDone = batch.status === 'completed';

  if (el.tasksBatchStatusBadge) {
    el.tasksBatchStatusBadge.textContent = isDone ? 'Concluído' : (isStopped ? 'Interrompido' : 'Em andamento');
    el.tasksBatchStatusBadge.className = `badge ${isDone ? 'badge-success' : (isStopped ? 'badge-danger' : 'badge-indigo')}`;
  }
}

function updateTaskCardBadges(batch) {
  if (!batch || !batch.tasks) return;
  for (const [tid, tinfo] of Object.entries(batch.tasks)) {
    const card = document.querySelector(`.task-card[data-id="${tid}"]`);
    if (!card) continue;
    const badgeContainer = card.querySelector('.task-card-header-right');
    if (!badgeContainer) continue;

    let existingBadge = badgeContainer.querySelector('.task-batch-live-badge');
    if (!existingBadge) {
      existingBadge = document.createElement('span');
      existingBadge.className = 'badge task-batch-live-badge';
      badgeContainer.insertBefore(existingBadge, badgeContainer.firstChild);
    }

    if (tinfo.status === 'resolving_ai') {
      existingBadge.className = 'badge badge-warning task-batch-live-badge';
      existingBadge.textContent = 'IA Resolvendo...';
    } else if (tinfo.status === 'waiting_delay') {
      existingBadge.className = 'badge badge-indigo task-batch-live-badge';
      existingBadge.textContent = `Delay (${tinfo.remaining_seconds}s)`;
    } else if (tinfo.status === 'submitting') {
      existingBadge.className = 'badge badge-warning task-batch-live-badge';
      existingBadge.textContent = 'Enviando...';
    } else if (tinfo.status === 'completed') {
      existingBadge.className = 'badge badge-success task-batch-live-badge';
      existingBadge.textContent = tinfo.score !== null && tinfo.score !== undefined ? `Nota ${tinfo.score}` : 'Concluído';
    } else if (tinfo.status === 'failed') {
      existingBadge.className = 'badge badge-danger task-batch-live-badge';
      existingBadge.textContent = 'Falhou';
    } else if (tinfo.status === 'stopped') {
      existingBadge.className = 'badge badge-danger task-batch-live-badge';
      existingBadge.textContent = 'Interrompido';
    }
  }
}

async function checkActiveTasksBatch() {
  try {
    const res = await fetch('/api/tasks/active-batch');
    if (!res.ok) return;
    const data = await res.json();
    if (data.active && data.batch) {
      state.activeTaskBatch = data.batch;
      renderActiveTasksBatchBanner(data.batch);
      pollTasksBatch(data.batch.id);
    }
  } catch (err) {}
}

async function stopTasksBatch() {
  if (!state.activeTaskBatch) return;
  try {
    await fetch(`/api/tasks/batch/${state.activeTaskBatch.id}/stop`, { method: 'POST' });
    showToast('Comando de cancelamento do lote enviado.', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
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

async function loadLeiaSPData() {
  if (el.leiaspGrid) {
    el.leiaspGrid.innerHTML = '<div class="loading-state" style="grid-column:1/-1;"><div class="spinner"></div><p>Carregando biblioteca do LeiaSP...</p></div>';
  }
  try {
    const res = await fetch('/api/leiasp/books');
    if (!res.ok) throw new Error('Falha ao carregar livros do LeiaSP.');
    const data = await res.json();
    state.leiaspBooks = data.books || [];

    const total = state.leiaspBooks.length;
    const completed = state.leiaspBooks.filter(b => b.is_complete || b.progress >= 100).length;
    const pending = total - completed;

    if (el.badgeLeiaSPCount) el.badgeLeiaSPCount.textContent = pending;
    if (el.leiaspStatTotal) el.leiaspStatTotal.textContent = total;
    if (el.leiaspStatCompleted) el.leiaspStatCompleted.textContent = completed;
    if (el.leiaspStatPending) el.leiaspStatPending.textContent = pending;

    renderLeiaSPBooks();
    checkActiveLeiaSPJob();
  } catch (err) {
    if (el.leiaspGrid) {
      el.leiaspGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><p style="color:var(--danger);">Erro ao carregar livros: ${err.message}</p></div>`;
    }
  }
}

function renderLeiaSPBooks() {
  if (!el.leiaspGrid) return;
  if (state.leiaspBooks.length === 0) {
    el.leiaspGrid.innerHTML = '<div class="empty-state" style="grid-column:1/-1;"><p>Nenhum livro encontrado na biblioteca do LeiaSP.</p></div>';
    return;
  }

  const activeBookId = state.activeLeiaSPJob && state.activeLeiaSPJob.status === 'running' ? state.activeLeiaSPJob.book_id : null;

  el.leiaspGrid.innerHTML = state.leiaspBooks.map(book => {
    const isDone = book.is_complete || book.progress >= 100;
    const isCurrentlyReading = activeBookId && (book.id === activeBookId);
    const statusBadge = isDone
      ? '<span class="task-badge badge-success">Concluído</span>'
      : (book.progress > 0 ? `<span class="task-badge badge-warning">${book.progress}% lido</span>` : '<span class="task-badge badge-indigo">Pendente</span>');

    const coverImg = book.cover_url
      ? `<img src="${book.cover_url}" alt="${book.title}" class="book-cover-img" loading="lazy" onerror="this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';"><div class="book-cover-placeholder" style="display:none;"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg></div>`
      : `<div class="book-cover-placeholder"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg></div>`;

    const pagesDisplay = book.total_pages > 0
      ? (book.current_page > 0 ? `${book.current_page}/${book.total_pages}` : `${book.total_pages}`)
      : 'Pendente';

    return `
      <div class="leiasp-card glass-panel ${isCurrentlyReading ? 'reading-active' : ''}" data-book-id="${book.id}">
        <div class="book-cover-wrapper">
          ${coverImg}
          <div class="book-cover-overlay">
            <span class="book-level-badge">${book.level || book.genre || 'Leitura'}</span>
          </div>
        </div>
        <div class="book-info">
          <div class="book-header">
            ${statusBadge}
            ${book.is_quiz_active ? '<span class="quiz-badge" title="Contém quiz avaliativo">Quiz</span>' : ''}
          </div>
          <h4 class="book-title" title="${book.title}">${book.title}</h4>
          <p class="book-author">${book.author || 'Autor Desconhecido'}</p>
          <div class="book-meta">
            <span>Páginas: <strong>${pagesDisplay}</strong></span>
            <span>Progresso: <strong>${book.progress}%</strong></span>
          </div>
          <div class="progress-bar-bg" style="background: rgba(255,255,255,0.06); height: 5px; border-radius: 3px; overflow: hidden; margin: 8px 0;">
            <div style="width: ${book.progress}%; height: 100%; background: ${isDone ? 'var(--success)' : 'var(--primary)'};"></div>
          </div>
          <button class="btn btn-primary btn-sm btn-block btn-read-book" data-book-id="${book.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            <span>${isDone ? 'Ler Novamente' : (book.progress > 0 ? 'Continuar Leitura' : 'Iniciar Leitura')}</span>
          </button>
        </div>
      </div>
    `;
  }).join('');

  el.leiaspGrid.querySelectorAll('.btn-read-book').forEach(btn => {
    btn.addEventListener('click', () => {
      const bookId = parseInt(btn.dataset.bookId);
      const book = state.leiaspBooks.find(b => b.id === bookId);
      if (book) openLeiaSPModal(book, false);
    });
  });
}

async function checkActiveLeiaSPJob() {
  try {
    const res = await fetch('/api/leiasp/active-job');
    if (!res.ok) return;
    const data = await res.json();
    if (data.active && data.job) {
      state.currentLeiaSPJobId = data.job.id;
      state.activeLeiaSPJob = data.job;
      renderActiveLeiaSPBanner(data.job);
      pollLeiaSPJob(data.job.id);
    } else {
      hideActiveLeiaSPBanner();
    }
  } catch (err) {}
}

function renderActiveLeiaSPBanner(job) {
  if (!el.leiaspActiveBanner || !job) return;
  el.leiaspActiveBanner.classList.remove('hidden');

  if (el.activeBannerTitle) el.activeBannerTitle.textContent = job.book_title || 'Leitura de Livro';

  if (el.activeBannerCover) {
    if (job.book_cover_url) {
      el.activeBannerCover.src = job.book_cover_url;
      el.activeBannerCover.style.display = 'block';
      if (el.activeBannerCoverFallback) el.activeBannerCoverFallback.style.display = 'none';
    } else {
      el.activeBannerCover.style.display = 'none';
      if (el.activeBannerCoverFallback) el.activeBannerCoverFallback.style.display = 'flex';
    }
  }

  const percent = job.progress_percent || 0;
  if (el.activeBannerPercent) el.activeBannerPercent.textContent = `${percent}%`;
  if (el.activeBannerProgressBar) el.activeBannerProgressBar.style.width = `${percent}%`;
  if (el.activeBannerPage) el.activeBannerPage.textContent = `${job.current_page || 0}/${job.total_pages || 0}`;

  if (job.logs && job.logs.length > 0 && el.activeBannerLastLog) {
    el.activeBannerLastLog.textContent = job.logs[job.logs.length - 1];
  }

  if (job.sequential && job.queue_total > 0 && el.activeBannerQueueBadge) {
    el.activeBannerQueueBadge.textContent = `Livro ${job.queue_current_idx || 1}/${job.queue_total}`;
    el.activeBannerQueueBadge.classList.remove('hidden');
  } else if (el.activeBannerQueueBadge) {
    el.activeBannerQueueBadge.classList.add('hidden');
  }

  const isPaused = job.status === 'paused';
  const isRunning = job.status === 'running';

  if (el.activeBannerStatus) {
    el.activeBannerStatus.textContent = isPaused ? 'Leitura Pausada' : (isRunning ? 'Lendo em segundo plano...' : (job.status === 'completed' ? 'Leitura Concluída!' : 'Leitura Interrompida'));
    el.activeBannerStatus.style.color = isPaused ? '#f59e0b' : (job.status === 'stopped' ? '#ef4444' : '#10b981');
  }

  const playSvg = '<polygon points="5 3 19 12 5 21 5 3"></polygon>';
  const pauseSvg = '<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>';

  if (el.btnBannerPauseText && el.iconBannerPause) {
    el.btnBannerPauseText.textContent = isPaused ? 'Retomar' : 'Pausar';
    el.iconBannerPause.innerHTML = isPaused ? playSvg : pauseSvg;
  }

  if (el.btnModalPauseText && el.iconModalPause) {
    el.btnModalPauseText.textContent = isPaused ? 'Retomar Leitura' : 'Pausar Leitura';
    el.iconModalPause.innerHTML = isPaused ? playSvg : pauseSvg;
  }
}

function hideActiveLeiaSPBanner() {
  if (el.leiaspActiveBanner) el.leiaspActiveBanner.classList.add('hidden');
  if (el.leiaspGrid) {
    el.leiaspGrid.querySelectorAll('.leiasp-card.reading-active').forEach(c => c.classList.remove('reading-active'));
  }
}

function openLeiaSPModal(book, isSequential = false) {
  state.selectedLeiaSPBook = book;
  state.isSequentialLeiaSP = isSequential;

  if (isSequential) {
    if (el.leiaspBookNameInput) el.leiaspBookNameInput.value = 'Fila Sequencial (Todos os livros incompletos da conta)';
    if (el.leiaspModalTitle) el.leiaspModalTitle.textContent = 'Leitura Sequencial em Fila';
  } else if (book) {
    const pagesInfo = book.total_pages > 0 ? `${book.total_pages} págs` : 'Pendente';
    const curInfo = book.current_page > 0 ? ` - atual: pág ${book.current_page}` : '';
    if (el.leiaspBookNameInput) el.leiaspBookNameInput.value = `${book.title} (${pagesInfo}${curInfo})`;
    if (el.leiaspModalTitle) el.leiaspModalTitle.textContent = 'Leitura Humanizada de Livro';
  }

  if (el.leiaspConfigView) el.leiaspConfigView.classList.remove('hidden');
  if (el.leiaspProgressView) el.leiaspProgressView.classList.add('hidden');
  if (el.modalLeiaSPReader) el.modalLeiaSPReader.classList.remove('hidden');
}

function openLeiaSPMonitorModal() {
  if (el.leiaspConfigView) el.leiaspConfigView.classList.add('hidden');
  if (el.leiaspProgressView) el.leiaspProgressView.classList.remove('hidden');
  if (el.modalLeiaSPReader) el.modalLeiaSPReader.classList.remove('hidden');
  if (state.activeLeiaSPJob && el.leiaspModalTitle) {
    el.leiaspModalTitle.textContent = state.activeLeiaSPJob.sequential ? 'Monitor de Leitura Sequencial' : 'Monitor de Telemetria LeiaSP';
  }
}

function closeLeiaSPModal() {
  if (el.modalLeiaSPReader) el.modalLeiaSPReader.classList.add('hidden');
}

async function startLeiaSPReading() {
  const minTime = parseInt(el.leiaspMinTime.value) || 20;
  const maxTime = parseInt(el.leiaspMaxTime.value) || 40;
  const autoQuiz = el.leiaspAutoQuiz.checked;

  const payload = {
    book_id: state.isSequentialLeiaSP ? null : (state.selectedLeiaSPBook ? state.selectedLeiaSPBook.id : null),
    pages_to_read: 0,
    min_time: minTime,
    max_time: maxTime,
    auto_solve_quiz: autoQuiz,
    sequential: state.isSequentialLeiaSP,
  };

  el.btnStartLeiaSPRead.disabled = true;

  try {
    const res = await fetch('/api/leiasp/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao iniciar leitura.');

    state.currentLeiaSPJobId = data.job_id;
    showToast(data.message || 'Leitura iniciada com sucesso em segundo plano!', 'success');

    el.leiaspConfigView.classList.add('hidden');
    el.leiaspProgressView.classList.remove('hidden');
    el.leiaspLogsBox.innerHTML = '<div class="log-line text-muted">Job iniciado. Conectando telemetria...</div>';

    pollLeiaSPJob(data.job_id);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    el.btnStartLeiaSPRead.disabled = false;
  }
}

function pollLeiaSPJob(jobId) {
  if (state.leiaspJobPollInterval) {
    clearInterval(state.leiaspJobPollInterval);
  }

  state.leiaspJobPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/leiasp/job/${jobId}`);
      if (!res.ok) {
        clearInterval(state.leiaspJobPollInterval);
        state.leiaspJobPollInterval = null;
        return;
      }

      const data = await res.json();
      const job = data.job;
      if (!job) return;

      state.activeLeiaSPJob = job;
      renderActiveLeiaSPBanner(job);

      const percent = job.progress_percent || 0;
      if (el.leiaspJobPercent) el.leiaspJobPercent.textContent = `${percent}%`;
      if (el.leiaspProgressBar) el.leiaspProgressBar.style.width = `${percent}%`;
      if (el.leiaspPageCounter) el.leiaspPageCounter.textContent = `${job.current_page || 0}/${job.total_pages || 0}`;
      
      const isPaused = job.status === 'paused';
      if (el.leiaspJobState) {
        el.leiaspJobState.textContent = isPaused ? 'Pausado' : (job.status === 'running' ? 'Em andamento' : (job.status === 'completed' ? 'Concluído' : job.status));
      }

      if (el.leiaspJobStatusText) {
        if (isPaused) {
          el.leiaspJobStatusText.textContent = `Pausado em '${job.book_title || 'Livro'}'`;
        } else if (job.status === 'running') {
          el.leiaspJobStatusText.textContent = `Lendo '${job.book_title || 'Livro'}'...`;
        } else if (job.status === 'completed') {
          el.leiaspJobStatusText.textContent = 'Leitura Concluída!';
        } else if (job.status === 'stopped') {
          el.leiaspJobStatusText.textContent = 'Leitura Interrompida';
        }
      }

      if (job.logs && el.leiaspLogsBox) {
        el.leiaspLogsBox.innerHTML = job.logs.map(l => `<div class="log-line">${l}</div>`).join('');
        el.leiaspLogsBox.scrollTop = el.leiaspLogsBox.scrollHeight;
      }

      if (job.status === 'completed' || job.status === 'failed' || job.status === 'stopped') {
        clearInterval(state.leiaspJobPollInterval);
        state.leiaspJobPollInterval = null;
        state.currentLeiaSPJobId = null;

        if (job.status === 'completed') {
          showToast('Leitura e quizzes do LeiaSP finalizados com sucesso!', 'success');
        } else if (job.status === 'stopped') {
          showToast('Leitura interrompida.', 'info');
        }

        setTimeout(() => {
          hideActiveLeiaSPBanner();
          loadLeiaSPData();
        }, 4000);
      }
    } catch (err) {}
  }, 1200);
}

async function togglePauseResumeLeiaSP() {
  const jobId = state.currentLeiaSPJobId || (state.activeLeiaSPJob ? state.activeLeiaSPJob.id : null);
  if (!jobId) return;

  const isPaused = state.activeLeiaSPJob && state.activeLeiaSPJob.status === 'paused';
  const endpoint = isPaused ? `/api/leiasp/job/${jobId}/resume` : `/api/leiasp/job/${jobId}/pause`;

  try {
    const res = await fetch(endpoint, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao alternar pausa.');
    
    if (state.activeLeiaSPJob) {
      state.activeLeiaSPJob.status = isPaused ? 'running' : 'paused';
      renderActiveLeiaSPBanner(state.activeLeiaSPJob);
    }
    showToast(isPaused ? 'Leitura retomada!' : 'Leitura pausada!', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function stopLeiaSPReading() {
  const jobId = state.currentLeiaSPJobId || (state.activeLeiaSPJob ? state.activeLeiaSPJob.id : null);
  if (!jobId) return;

  try {
    await fetch(`/api/leiasp/job/${jobId}/stop`, { method: 'POST' });
    showToast('Comando de parada enviado.', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
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

  if (el.tasksSelectAll) {
    el.tasksSelectAll.addEventListener('change', (e) => {
      const checked = e.target.checked;
      state.selectedTaskIds.clear();
      if (checked) {
        state.tasks.forEach(t => state.selectedTaskIds.add(t.id));
      }
      renderFilteredTasks();
    });
  }
  if (el.btnBatchSolveTasks) el.btnBatchSolveTasks.addEventListener('click', startTasksBatchSolve);
  if (el.btnTasksBatchStop) el.btnTasksBatchStop.addEventListener('click', stopTasksBatch);

  if (el.btnRefreshLeiaSP) el.btnRefreshLeiaSP.addEventListener('click', loadLeiaSPData);
  if (el.btnLeiaSPSeq) el.btnLeiaSPSeq.addEventListener('click', () => openLeiaSPModal(null, true));
  if (el.btnCloseLeiaSPModal) el.btnCloseLeiaSPModal.addEventListener('click', closeLeiaSPModal);
  if (el.btnStartLeiaSPRead) el.btnStartLeiaSPRead.addEventListener('click', startLeiaSPReading);
  if (el.btnStopLeiaSPRead) el.btnStopLeiaSPRead.addEventListener('click', stopLeiaSPReading);
  if (el.btnModalPauseResume) el.btnModalPauseResume.addEventListener('click', togglePauseResumeLeiaSP);
  if (el.btnModalMinimize) el.btnModalMinimize.addEventListener('click', closeLeiaSPModal);

  if (el.btnBannerPauseResume) el.btnBannerPauseResume.addEventListener('click', togglePauseResumeLeiaSP);
  if (el.btnBannerStop) el.btnBannerStop.addEventListener('click', stopLeiaSPReading);
  if (el.btnBannerOpenModal) el.btnBannerOpenModal.addEventListener('click', openLeiaSPMonitorModal);

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
      if (el.modalTask && !el.modalTask.classList.contains('hidden')) closeModal();
      if (el.modalMatificSim && !el.modalMatificSim.classList.contains('hidden')) closeMatificModal();
      if (el.modalMatificStats && !el.modalMatificStats.classList.contains('hidden')) el.modalMatificStats.classList.add('hidden');
      if (el.modalLeiaSPReader && !el.modalLeiaSPReader.classList.contains('hidden')) closeLeiaSPModal();
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
