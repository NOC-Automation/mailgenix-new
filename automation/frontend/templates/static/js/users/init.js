// static/js/users/init.js

  import { getCsrfToken } from '../utils.js';

  // -----------------------------------------------------------------------
  // CONFIG
  // -----------------------------------------------------------------------
  const API = {
    list:   '/api/users/',
    detail: (id) => `/api/users/${id}/`,
  };

  const DEFAULTS = {
    limit: 10,
    role:  'user',
  };

  const CSS = {
    hidden: 'hidden',
  };

  // -----------------------------------------------------------------------
  // UTILITIES
  // -----------------------------------------------------------------------

  /** Shorthand for querySelector with an optional root. */
  function qs(sel, root = document) {
    return root.querySelector(sel);
  }

  /** Lowercase + trim a value for comparison. */
  function normalizeText(value) {
    return (value || '').toString().trim().toLowerCase();
  }

  /**
   * Build a single searchable string from a user object.
   * All fields are concatenated so one `.includes()` call covers everything.
   */
  function buildSearchBlob(user) {
    return [
      user.id,
      user.username,
      user.role,
      user.is_active ? 'yes active true' : 'no inactive false',
      user.last_login || '',
    ].join(' ').toLowerCase();
  }

  // -----------------------------------------------------------------------
  // HTML TEMPLATES
  // -----------------------------------------------------------------------

  /** Action buttons injected into each table row. */
  function tplActionButtons(id) {
    return `
      <div class="flex items-center gap-3">
        <button class="user-edit" type="button" aria-label="Edit User"
                data-action="user-edit" data-id="${id}">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
               class="h-5 w-5 text-indigo-600 pointer-events-none"
               fill="none" stroke="currentColor" stroke-width="1.8"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 21l3.75-.75L20 7.06a2.12 2.12 0 10-3-3L3.75 17.25 3 21z"/>
            <path d="M14.5 5.5l4 4"/>
          </svg>
        </button>
        <button class="user-delete" type="button" aria-label="Delete User"
                data-action="user-delete" data-id="${id}">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
               class="h-5 w-5 text-rose-600 pointer-events-none"
               fill="none" stroke="currentColor" stroke-width="1.8"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 6h18"/>
            <path d="M8 6V4.8A1.8 1.8 0 019.8 3h4.4A1.8 1.8 0 0116 4.8V6"/>
            <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
          </svg>
        </button>
      </div>
    `;
  }

  /** Single table row. */
  function tplUserRow(u) {
    const role = normalizeText(u.role) === 'admin' ? 'Admin' : 'User';
    const roleTone = role === 'Admin' ? 'admin' : 'user';
    const status = u.is_active ? 'Active' : 'Inactive';
    return `
      <tr data-id="${u.id}" data-role="${normalizeText(u.role)}" class="hover:bg-gray-50">
        <td class="px-4 py-3 text-sm text-gray-700">${u.id}</td>
        <td class="px-4 py-3 text-sm font-medium text-gray-800">${u.username}</td>
        <td class="px-4 py-3 text-sm"><span class="mg-role-badge ${roleTone}">${role}</span></td>
        <td class="px-4 py-3 text-sm"><span class="mg-role-badge ${u.is_active ? 'active' : 'inactive'}">${status}</span></td>
        <td class="px-4 py-3 text-sm text-gray-600">${u.last_login || '-'}</td>
        <td class="px-4 py-3 text-sm">${tplActionButtons(u.id)}</td>
      </tr>
    `;
  }

  /** Empty-state row spanning all columns. */
  function tplEmptyRow(message, isError = false) {
    const color = isError ? 'text-red-600' : 'text-gray-500';
    return `
      <tr>
        <td colspan="6" class="px-4 py-6 text-center text-sm ${color}">
          ${message}
        </td>
      </tr>
    `;
  }

  /** Single pagination button. */
  function tplPageButton(label, page, { disabled = false, active = false } = {}) {
    const base    = 'h-8 min-w-[2rem] rounded border px-3 text-sm';
    const style   = active
      ? 'border-sky-600 bg-sky-600 text-white'
      : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50';
    const dimmed  = disabled ? 'opacity-50 cursor-not-allowed' : '';

    return `
      <button type="button" class="${base} ${style} ${dimmed}"
              data-page="${page}" ${disabled ? 'disabled' : ''}>
        ${label}
      </button>
    `;
  }

  // -----------------------------------------------------------------------
  // MAIN EXPORT
  // -----------------------------------------------------------------------
  export function initUsersPage() {

    // -----------------------------------------------------------------------
    // DOM ELEMENTS
    // -----------------------------------------------------------------------
    const app = qs('#users-app');
    if (!app) return;

    // Double-init guard
    if (app.dataset.initialized === '1') return;
    app.dataset.initialized = '1';

    const els = {
      form:             qs('#user-form',        app),
      fId:              qs('#u-id',             app),
      fUsername:        qs('#u-username',       app),
      fPassword:        qs('#u-password',       app),
      fRole:            qs('#u-role',           app),
      fActive:          qs('#u-active',         app),
      tbody:            qs('#users-tbody',      app),
      searchInput:      qs('#userSearch',       app),
      showEntries:      qs('#userShowEntries',  app),
      summary:          qs('#users-summary',    app),
      pagination:       qs('#users-pagination', app),
      modal:            qs('#user-modal'),
      modalTitle:       qs('#modal-title'),
      btnAdd:           qs('#btn-add-user'),
      btnCancel:        qs('#modal-cancel'),
    };

    // -----------------------------------------------------------------------
    // STATE
    // -----------------------------------------------------------------------
    const state = {
      rows:    [],
      search:  '',
      limit:   Number(els.showEntries?.value || DEFAULTS.limit),
      page:    1,
    };

    // -----------------------------------------------------------------------
    // FORM HELPERS
    // -----------------------------------------------------------------------

    function resetForm() {
      if (els.fId)       els.fId.value       = '';
      if (els.fUsername) els.fUsername.value = '';
      if (els.fPassword) els.fPassword.value = '';
      if (els.fRole)     els.fRole.value     = DEFAULTS.role;
      if (els.fActive)   els.fActive.checked = true;
    }

    function readFormPayload() {
      return {
        username:  els.fUsername?.value.trim(),
        password:  els.fPassword?.value,
        role:      els.fRole?.value,
        is_active: !!(els.fActive?.checked),
      };
    }

    // -----------------------------------------------------------------------
    // MODAL HELPERS
    // -----------------------------------------------------------------------

    function openModal(isEdit = false) {
      if (!els.modal) return;
      if (els.modalTitle) els.modalTitle.textContent = isEdit ? 'Edit User' : 'Add User';
      els.modal.classList.remove(CSS.hidden);
    }

    function closeModal() {
      els.modal?.classList.add(CSS.hidden);
    }

    // -----------------------------------------------------------------------
    // TABLE RENDERING
    // -----------------------------------------------------------------------

    function renderRows(rows) {
      if (!els.tbody) return;
      els.tbody.innerHTML = rows.length
        ? rows.map(tplUserRow).join('')
        : tplEmptyRow('Belum ada user.');
    }

    function renderSummary(total) {
      if (!els.summary) return;
      if (total === 0) { els.summary.textContent = 'Showing 0 to 0 of 0 entries'; return; }
      const start = (state.page - 1) * state.limit + 1;
      const end   = Math.min(start + state.limit - 1, total);
      els.summary.textContent = `Showing ${start} to ${end} of ${total} entries`;
    }

    function renderPagination(total) {
      if (!els.pagination) return;
      const totalPages = getTotalPages(total);

      if (total === 0 || totalPages <= 1) { els.pagination.innerHTML = ''; return; }

      const buttons = [
        tplPageButton('Prev', state.page - 1, { disabled: state.page <= 1 }),
        ...Array.from({ length: totalPages }, (_, i) =>
          tplPageButton(String(i + 1), i + 1, { active: i + 1 === state.page })
        ),
        tplPageButton('Next', state.page + 1, { disabled: state.page >= totalPages }),
      ];

      els.pagination.innerHTML = buttons.join('');
    }

    // -----------------------------------------------------------------------
    // FILTERING + PAGINATION LOGIC
    // -----------------------------------------------------------------------

    function getTotalPages(total) {
      return Math.max(1, Math.ceil(total / state.limit));
    }

    function getFilteredRows() {
      const term = normalizeText(state.search);
      return term
        ? state.rows.filter((u) => buildSearchBlob(u).includes(term))
        : state.rows;
    }

    function getPagedRows(rows) {
      const start = (state.page - 1) * state.limit;
      return rows.slice(start, start + state.limit);
    }

    function refreshTable() {
      const filtered   = getFilteredRows();
      const total      = filtered.length;
      const totalPages = getTotalPages(total);

      if (state.page > totalPages) state.page = totalPages;

      renderRows(getPagedRows(filtered));
      renderSummary(total);
      renderPagination(total);
    }

    // -----------------------------------------------------------------------
    // API CALLS
    // -----------------------------------------------------------------------

    /** Show a loading/error placeholder in the table body. */
    function setTablePlaceholder(message, isError = false) {
      if (els.tbody)      els.tbody.innerHTML      = tplEmptyRow(message, isError);
      if (els.summary)    els.summary.textContent  = 'Showing 0 to 0 of 0 entries';
      if (els.pagination) els.pagination.innerHTML = '';
    }

    async function loadUsers() {
      setTablePlaceholder('Loading...');

      const res = await fetch(API.list, { credentials: 'same-origin' });

      if (!res.ok) {
        setTablePlaceholder(`Gagal memuat data (${res.status})`, true);
        return;
      }

      const data   = await res.json();
      state.rows   = Array.isArray(data.results) ? data.results : [];
      refreshTable();
    }

    async function saveUser(id, payload) {
      return fetch(id ? API.detail(id) : API.list, {
        method:  id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body:    JSON.stringify(payload),
        credentials: 'same-origin',
      });
    }

    async function deleteUser(id) {
      return fetch(API.detail(id), {
        method:  'DELETE',
        headers: { 'X-CSRFToken': getCsrfToken() },
        credentials: 'same-origin',
      });
    }

    // -----------------------------------------------------------------------
    // EVENT HANDLERS
    // -----------------------------------------------------------------------

    els.searchInput?.addEventListener('input', () => {
      state.search = els.searchInput.value || '';
      state.page   = 1;
      refreshTable();
    });

    els.showEntries?.addEventListener('change', () => {
      const parsed = Number(els.showEntries.value);
      state.limit  = Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULTS.limit;
      state.page   = 1;
      refreshTable();
    });

    els.pagination?.addEventListener('click', (e) => {
      const btn  = e.target.closest('button[data-page]');
      if (!btn || btn.disabled) return;

      const next = Number(btn.dataset.page);
      if (!Number.isFinite(next) || next < 1) return;

      state.page = next;
      refreshTable();
    });

    els.btnAdd?.addEventListener('click', () => {
      resetForm();
      openModal(false);
    });

    els.btnCancel?.addEventListener('click', () => {
      closeModal();
      resetForm();
    });

    // Delegate table row actions (edit + delete)
    els.tbody?.addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-action]');
      if (!btn) return;

      const tr = e.target.closest('tr[data-id]');
      const id = btn.dataset.id || tr?.dataset.id;
      if (!id) return;

      if (btn.dataset.action === 'user-edit') {
        handleEditClick(tr, id);
        return;
      }

      if (btn.dataset.action === 'user-delete') {
        await handleDeleteClick(btn, id);
      }
    });

    function handleEditClick(tr, id) {
      if (els.fId)       els.fId.value       = id;
      if (els.fUsername) els.fUsername.value = tr.children[1].textContent.trim();
      if (els.fPassword) els.fPassword.value = '';
      if (els.fRole)     els.fRole.value     = tr.dataset.role || DEFAULTS.role;
      if (els.fActive)   els.fActive.checked = tr.children[3].textContent.trim().toLowerCase().includes('active') && !tr.children[3].textContent.trim().toLowerCase().includes('inactive');
      openModal(true);
    }

    async function handleDeleteClick(btn, id) {
      if (!window.confirm('Hapus user ini?')) return;

      const prevHtml  = btn.innerHTML;
      btn.disabled    = true;
      btn.innerHTML   = '...';

      try {
        const res = await deleteUser(id);
        if (!res.ok) { alert(`Gagal hapus: ${res.status} ${await res.text()}`); return; }
        await loadUsers();
        resetForm();
      } catch (err) {
        alert(`Gagal hapus: ${String(err)}`);
      } finally {
        btn.disabled  = false;
        btn.innerHTML = prevHtml;
      }
    }

    // Anti-double-submit guard
    let submitting = false;

    els.form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (submitting) return;
      submitting = true;

      const saveBtn = els.form.querySelector('button[type="submit"]');
      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }

      try {
        const id  = els.fId?.value.trim();
        const res = await saveUser(id, readFormPayload());

        if (!res.ok) { alert(`Gagal simpan: ${res.status} ${await res.text()}`); return; }

        await loadUsers();
        closeModal();
        resetForm();
      } catch (err) {
        alert(`Gagal simpan: ${String(err)}`);
      } finally {
        submitting = false;
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }
      }
    });

    // -----------------------------------------------------------------------
    // INITIAL LOAD
    // -----------------------------------------------------------------------
    loadUsers().catch((err) => setTablePlaceholder(String(err), true));
  }
// test flow