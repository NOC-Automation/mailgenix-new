// static/js/tenantList/events.js
// Modern Tenant List events
// - group-edit: redirect ke /tenants/add/?mode=edit...
// - row-delete: putus relasi Customer ↔ Rack untuk satu baris
// - legacy modal save tetap dipertahankan sementara agar tidak mem-break flow lama

import { debounce, bindModalDismiss, showConfirm, showToast } from './utils.js';
import { persistTenantListState } from './state.js';
import { filterData } from './data.js';
import { handleSaveClick, handleActionClick } from './actions.js';

export function bindInputs(store, dom, render) {
  // Show entries (perPage)
  if (dom.showSelect && !dom.showSelect.dataset.bound) {
    dom.showSelect.dataset.bound = '1';

    dom.showSelect.addEventListener('change', async () => {
      store.state.perPage = parseInt(dom.showSelect.value, 10);
      store.state.page = 1;

      persistTenantListState(store);

      if (store.state.serverMode) {
        await dom.api.loadFromServer(store);
      }

      render();
    });
  }

  // Search
  if (dom.searchInput && !dom.searchInput.dataset.bound) {
    dom.searchInput.dataset.bound = '1';

    let searchAbort = null;

    const onSearch = debounce(async (e) => {
      store.state.search = e.target.value ?? '';
      store.state.page = 1;

      persistTenantListState(store);

      if (store.state.serverMode) {
        if (searchAbort) searchAbort.abort();
        searchAbort = new AbortController();

        try {
          await dom.api.loadFromServer(store, { signal: searchAbort.signal });
        } catch (err) {
          if (err.name !== 'AbortError') throw err;
        }
      }

      render();
    }, 150);

    dom.searchInput.addEventListener('input', onSearch);
  }

  // Save di modal legacy (dipertahankan sementara agar tidak mem-break halaman lama)
  if (dom.saveBtn && !dom.saveBtn.dataset.bound) {
    dom.saveBtn.dataset.bound = '1';
    dom.saveBtn.addEventListener('click', (e) => {
      e.preventDefault();
      handleSaveClick(store, dom, dom.api, render);
    });
  }

  if (dom.editForm && !dom.editForm.dataset.bound) {
    dom.editForm.dataset.bound = '1';
    dom.editForm.addEventListener('submit', (e) => {
      e.preventDefault();
      dom.saveBtn?.click();
    });
  }

  // Tombol add → arahkan ke halaman create
  const addBtn = document.getElementById('addCustomerBtn');
  if (addBtn && !addBtn.dataset.bound) {
    addBtn.dataset.bound = '1';
    addBtn.addEventListener('click', () => {
      window.location.href = '/tenants/add/?mode=create';
    });
  }
}

export function bindPagination(store, dom, render) {
  if (dom.paginationEl && !dom.paginationEl.dataset.bound) {
    dom.paginationEl.dataset.bound = '1';

    dom.paginationEl.addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-page]');
      if (!btn) return;

      const val = btn.getAttribute('data-page');

      let totalPages;
      if (store.state.serverMode) {
        const total = store.state.total ?? 0;
        const per = Math.max(1, store.state.perPage ?? 10);
        totalPages = Math.max(1, Math.ceil(total / per));
      } else {
        const filtered = filterData(store);
        totalPages = Math.max(
          1,
          Math.ceil(filtered.length / Math.max(1, store.state.perPage ?? 10))
        );
      }

      if (val === 'first') {
        store.state.page = 1;
      } else if (val === 'prev') {
        store.state.page = Math.max(1, store.state.page - 1);
      } else if (val === 'next') {
        store.state.page = Math.min(totalPages, store.state.page + 1);
      } else if (val === 'last') {
        store.state.page = totalPages;
      } else {
        const num = parseInt(val, 10);
        if (!Number.isNaN(num)) {
          store.state.page = num;
        }
      }

      persistTenantListState(store);

      if (store.state.serverMode) {
        await dom.api.loadFromServer(store);
      }

      render();
    });
  }
}

export function delegateActions(store, dom, render) {
  const hosts = [dom.tableBody, dom.cardsContainer].filter(Boolean);
  if (!hosts.length) return;

  const handler = (e) => {
    if (window.IS_ADMIN !== true) return;

    const btn = e.target.closest('button[data-action][data-id]');
    if (!btn) return;

    const action = btn.getAttribute('data-action');
    const id = parseInt(btn.getAttribute('data-id'), 10);

    // === Edit grup/customer modern ===
    if (action === 'group-edit') {
      const groupId = btn.getAttribute('data-group-id');
      const rackId = btn.getAttribute('data-rack-id');

      const qs = new URLSearchParams({
        mode: 'edit',
        customer_id: String(id),
        ...(groupId ? { group_id: String(groupId) } : {}),
        ...(rackId ? { rack_id: String(rackId) } : {}),
      });

      window.location.href = `/tenants/add/?${qs.toString()}`;
      return;
    }

    // === Hapus satu baris Customer × Rack ===
    if (action === 'row-delete') {
      const rackId = parseInt(btn.getAttribute('data-rack-id'), 10);

      let name = '';
      let rack = '';

      try {
        const rows = Array.isArray(store.state.rows) ? store.state.rows : [];
        const row =
          rows.find((r) => r.customer_id === id && r.rack_id === rackId) ||
          rows.find((r) => r.customer_id === id);

        if (row) {
          name = row.customer_name || '';
          rack = row.rack_location || '';
        }
      } catch (_) {}

      const message =
        name && rack
          ? `Hapus baris tenant: ${name} (${rack})?`
          : 'Yakin menghapus baris ini?';

      showConfirm(
        message,
        async () => {
          try {
            // 1) Hapus relasi Customer–Rack (SATU baris)
            await dom.api.deleteRow(id, rackId);

            // 2) Muat data terbaru
            await dom.api.loadFromServer(store);

            // 3) Koreksi page kalau out-of-range
            const total = store.state.total ?? 0;
            const per = Math.max(1, store.state.perPage ?? 10);
            const totalPages = Math.max(1, Math.ceil(total / per));
            const desiredPage = total === 0 ? 1 : Math.min(store.state.page, totalPages);

            if (desiredPage !== store.state.page) {
              store.state.page = desiredPage;
              persistTenantListState(store);
              await dom.api.loadFromServer(store);
            }

            // 4) Render + toast
            render();
            showToast('Baris tenant berhasil dihapus.', 'success');
          } catch (err) {
            console.error('Row delete failed:', err);
            showToast('Gagal menghapus baris. Coba lagi.', 'error');
          }
        },
        'Hapus'
      );

      return;
    }

    // === Legacy fallback ===
    handleActionClick(store, e, dom, dom.api, render);
  };

  hosts.forEach((host) => {
    if (host.dataset.actionsBound === '1') return;
    host.dataset.actionsBound = '1';
    host.addEventListener('click', handler);
  });
}

export function bindResize(render) {
  if (window.__tenantListResizeBound__) return;
  window.__tenantListResizeBound__ = true;

  window.addEventListener('resize', debounce(() => render(), 150));
}

export function bindModal(dom) {
  if (!dom.editModal) return;
  bindModalDismiss(dom.editModal, 'tenantEditModal');
}


function setCsvModalOpen(dom, open) {
  if (!dom.csvModal) return;
  dom.csvModal.classList.toggle('hidden', !open);
  dom.csvModal.classList.toggle('flex', open);
}

function escapeCsvResult(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function bindCsvImport(store, dom, render) {
  if (!dom.csvImportBtn || dom.csvImportBtn.dataset.bound === '1') return;
  dom.csvImportBtn.dataset.bound = '1';

  const close = () => setCsvModalOpen(dom, false);

  dom.csvImportBtn.addEventListener('click', () => {
    if (dom.csvResult) {
      dom.csvResult.classList.add('hidden');
      dom.csvResult.innerHTML = '';
    }
    setCsvModalOpen(dom, true);
  });

  dom.csvCloseBtn?.addEventListener('click', close);
  dom.csvCancelBtn?.addEventListener('click', close);
  dom.csvModal?.addEventListener('click', (e) => {
    if (e.target === dom.csvModal) close();
  });

  dom.csvUploadBtn?.addEventListener('click', async () => {
    const file = dom.csvFile?.files?.[0];
    if (!file) {
      showToast('Pilih file CSV terlebih dahulu.', 'error');
      return;
    }

    const btn = dom.csvUploadBtn;
    const oldText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Importing...';

    try {
      const result = await dom.api.importCustomersCsv(file);
      const errors = Array.isArray(result.errors) ? result.errors : [];
      const successCount = Number(result.success_count || 0);
      const errorCount = Number(result.error_count || 0);

      if (dom.csvResult) {
        const errorHtml = errors.length
          ? `<div class="mt-2"><strong>Baris gagal:</strong><ul class="mt-1 list-disc pl-5">${errors.map((x) => `<li>Line ${escapeCsvResult(x.line)} - ${escapeCsvResult(x.customer_name || '-')}: ${escapeCsvResult(x.error)}</li>`).join('')}</ul></div>`
          : '<div class="mt-2 text-emerald-700">Tidak ada error.</div>';
        dom.csvResult.innerHTML = `<div><strong>Import selesai.</strong> Berhasil: ${successCount}, Gagal: ${errorCount}.</div>${errorHtml}`;
        dom.csvResult.classList.remove('hidden');
      }

      await dom.api.loadFromServer(store);
      render();
      showToast(`CSV selesai: ${successCount} berhasil, ${errorCount} gagal.`, errorCount ? 'warning' : 'success');
    } catch (err) {
      console.error('[CSV Import] failed:', err);
      showToast(err.message || 'Import CSV gagal.', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  });
}
