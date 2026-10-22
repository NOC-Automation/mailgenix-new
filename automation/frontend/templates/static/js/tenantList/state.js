// static/js/tenantList/state.js

function parsePositiveInt(value, fallback) {
  const num = Number(value);
  return Number.isFinite(num) && num > 0 ? num : fallback;
}

export function createInitialStore(
  perPageInit = 10,
  { storageKey = 'tenantListState' } = {}
) {
  // --- Restore dari localStorage ---
  let restored = {};

  try {
    const raw = localStorage.getItem(storageKey);
    if (raw) {
      restored = JSON.parse(raw) || {};
    }
  } catch (_) {
    // abaikan error localStorage / JSON parse
  }

  const page = parsePositiveInt(restored.page, 1);
  const perPage = parsePositiveInt(restored.perPage, parsePositiveInt(perPageInit, 10));
  const search = typeof restored.search === 'string' ? restored.search : '';

  return {
    state: {
      // Data utama dari server
      rows: [],
      total: 0,

      // State tampilan (restore jika ada)
      page,
      perPage,
      search,

      // Legacy modal edit (opsional; bisa dihapus nanti kalau tidak dipakai lagi)
      editingId: null,

      // Mode
      serverMode: false,

      // Simpan key agar mudah dipakai modul lain
      _storageKey: storageKey,
    },
  };
}

export function persistTenantListState(store) {
  const key = store?.state?._storageKey || 'tenantListState';

  const payload = {
    page: store?.state?.page ?? 1,
    perPage: store?.state?.perPage ?? 10,
    search: store?.state?.search ?? '',
  };

  try {
    localStorage.setItem(key, JSON.stringify(payload));
  } catch (_) {
    // abaikan error localStorage
  }
}
