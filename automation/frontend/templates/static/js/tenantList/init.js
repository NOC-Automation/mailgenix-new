// static/js/tenantList/init.js

import { isMobile, showToast } from './utils.js';
import { createInitialStore, persistTenantListState } from './state.js';
import * as api from './api.js';
import { filterData, paginate } from './data.js';
import { renderTable, renderCards, renderPagination, renderInfo } from './renderers.js';
import { bindInputs, bindPagination, delegateActions, bindResize, bindModal, bindCsvImport } from './events.js';

export function initTenantList() {
  const dom = {
    showSelect: document.getElementById('tenantShowEntries'),
    searchInput: document.getElementById('tenantSearch'),
    paginationEl: document.getElementById('tenantPagination'),
    infoEl: document.getElementById('tenantTableInfo'),
    tableBody: document.getElementById('tenantTableBody'),
    cardsContainer: document.getElementById('tenantCards'),
    csvImportBtn: document.getElementById('importCustomerCsvBtn'),
    csvModal: document.getElementById('customerCsvModal'),
    csvCloseBtn: document.getElementById('customerCsvClose'),
    csvCancelBtn: document.getElementById('customerCsvCancel'),
    csvFile: document.getElementById('customerCsvFile'),
    csvUploadBtn: document.getElementById('customerCsvUpload'),
    csvResult: document.getElementById('customerCsvResult'),

    // (Legacy edit modal — opsional)
    editModal: document.getElementById('tenantEditModal'),
    editForm: document.getElementById('tenantEditForm'),
    tenantModalTitle: document.getElementById('tenantModalTitle'),
    saveBtn: document.getElementById('saveTenantBtn'),
    editRackLocation: document.getElementById('editRackLocation'),
    editCustomerName: document.getElementById('editCustomerName'),
    editAuthorizedPerson: document.getElementById('editAuthorizedPerson'),
    editEmail: document.getElementById('editEmail'),
    editPhone: document.getElementById('editPhone'),
    editDate: document.getElementById('editDate'),
    editValidity: document.getElementById('editValidity'),

    api,
  };

  // Halaman ini bukan Tenant List → jangan init
  if (!dom.tableBody && !dom.cardsContainer) {
    return;
  }

  // Scoped init guard
  const root =
    dom.tableBody?.parentElement ||
    dom.cardsContainer?.parentElement ||
    null;

  if (root?.dataset.initialized === '1') return;
  if (root) root.dataset.initialized = '1';

  // Ambil perPage awal dari dropdown (jika ada), gunakan untuk init
  const perPageInit = parseInt(dom.showSelect?.value ?? '10', 10);

  // Buat store + restore state dari localStorage
  const store = createInitialStore(perPageInit, { storageKey: 'tenantListState' });

  // Sinkronkan nilai input UI dengan state hasil restore
  if (dom.showSelect) dom.showSelect.value = String(store.state.perPage);
  if (dom.searchInput) dom.searchInput.value = store.state.search || '';

  // Fungsi render utama
  const render = () => {
    const filtered = filterData(store);
    const { slice, total, current, totalPages, start, end } =
    paginate(
      filtered,
      store.state.page,
      store.state.perPage,
      store.state.total,
      { serverMode: !!store.state.serverMode }
    );

    if (isMobile()) {
      renderCards(dom.cardsContainer, slice, store.state.search);
      if (dom.tableBody) dom.tableBody.innerHTML = '';
    } else {
      renderTable(dom.tableBody, slice, store.state.search);
      if (dom.cardsContainer) dom.cardsContainer.innerHTML = '';
    }

    renderInfo(dom.infoEl, start, end, total);
    renderPagination(dom.paginationEl, current, totalPages);
  };

  // Koreksi page jika page restore > totalPages terbaru
  async function ensureValidPageAndReload() {
    const total = store.state.total ?? 0;
    const per = Math.max(1, store.state.perPage ?? 10);
    const totalPages = Math.max(1, Math.ceil(total / per));

    const desiredPage = total === 0 ? 1 : Math.min(store.state.page, totalPages);

    if (desiredPage !== store.state.page) {
      store.state.page = desiredPage;
      persistTenantListState(store);
      await dom.api.loadFromServer(store);
    }
  }

  // Bind semua event
  bindModal(dom);
  bindCsvImport(store, dom, render);
  bindInputs(store, dom, render);
  bindPagination(store, dom, render);
  delegateActions(store, dom, render);
  bindResize(render);

  // Server mode + initial load
  store.state.serverMode = true;

  dom.api.loadFromServer(store)
    .then(async () => {
      await ensureValidPageAndReload();
      render();

      // FLASH TOAST: tampilkan pesan sukses setelah redirect dari halaman Edit
      try {
        const msg = sessionStorage.getItem('tenantToastMessage');
        const typ = sessionStorage.getItem('tenantToastType') || 'success';
        if (msg) {
          showToast(msg, typ);
          sessionStorage.removeItem('tenantToastMessage');
          sessionStorage.removeItem('tenantToastType');
        }
      } catch (_) {}
    })
    .catch((e) => {
      console.error('[TenantList] initial load failed:', e);
      showToast('Gagal memuat data tenant.', 'error');
      render();
    });
}
