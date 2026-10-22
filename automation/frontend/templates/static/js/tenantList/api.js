// static/js/tenantList/api.js
// Tenant List API module
// - Modern flow utama: by-customer / grouped tenant operations
// - Legacy single-AR CRUD dipertahankan sementara sebagai fallback

import { getCsrfToken } from './utils.js';

const BASE = '/api/tenants/';
const GROUP_BASE = '/api/tenants/by-customer/';

async function safeReadText(res) {
  try {
    return await res.text();
  } catch (_) {
    return '';
  }
}

function safeParseJson(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (_) {
    return null;
  }
}

async function buildErrorMessage(res, fallback) {
  const text = await safeReadText(res);
  const json = safeParseJson(text);
  return json?.detail || json?.error || fallback || `Request failed: ${res.status}`;
}

async function requestJson(url, { method = 'GET', headers = {}, body, signal } = {}) {
  const res = await fetch(url, {
    method,
    headers,
    body,
    signal,
    credentials: 'same-origin',
  });

  if (!res.ok) {
    throw new Error(await buildErrorMessage(res, `${method} failed: ${res.status}`));
  }

  const text = await safeReadText(res);
  return safeParseJson(text) ?? {};
}

async function requestOk(url, { method = 'GET', headers = {}, body, signal } = {}) {
  const res = await fetch(url, {
    method,
    headers,
    body,
    signal,
    credentials: 'same-origin',
  });

  if (!res.ok) {
    throw new Error(await buildErrorMessage(res, `${method} failed: ${res.status}`));
  }

  return true;
}

/**
 * Load Tenant List data dari server.
 * Dipakai oleh Tenant List modern (serverMode).
 */
export async function loadFromServer(store, { signal } = {}) {
  const params = new URLSearchParams({
    page: String(store.state.page ?? 1),
    per_page: String(store.state.perPage ?? 10),
    search: (store.state.search ?? '').trim(),
  });

  const url = `${BASE}?${params.toString()}`;
  const data = await requestJson(url, { method: 'GET', signal });

  const list = data.results ?? data.items ?? data.data ?? [];
  store.state.rows = Array.isArray(list) ? list : [];
  store.state.total = data.total ?? data.count ?? store.state.rows.length;

  return {
    results: store.state.rows,
    total: store.state.total,
  };
}

/* ------------------------------------------------------------------
 * LEGACY SINGLE-AR CRUD
 * Dipertahankan sementara untuk fallback lama (actions.js legacy).
 * Jangan hapus dulu sebelum dipastikan tidak ada lagi pemanggilnya.
 * ------------------------------------------------------------------ */

export async function createTenant(payload) {
  return requestJson(BASE, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

export async function updateTenant(id, payload) {
  return requestJson(`${BASE}${id}/`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

export async function deleteTenant(id) {
  return requestOk(`${BASE}${id}/`, {
    method: 'DELETE',
    headers: {
      'X-CSRFToken': getCsrfToken(),
    },
  });
}

/* ------------------------------------------------------------------
 * MODERN GROUP / BY-CUSTOMER ENDPOINTS
 * ------------------------------------------------------------------ */

/**
 * Fetch detail grouped/customer tenant untuk prefill edit page.
 */
export async function fetchGroup(customerId, groupId = null, rackId = null) {
  const params = new URLSearchParams();

  if (groupId) params.set('group_id', String(groupId));
  if (rackId) params.set('rack_id', String(rackId));

  const qs = params.toString() ? `?${params.toString()}` : '';
  return requestJson(`${GROUP_BASE}${customerId}/${qs}`, {
    method: 'GET',
  });
}

/**
 * Save/update grouped tenant by customer.
 */
export async function saveGroup(customerId, payload) {
  return requestJson(`${GROUP_BASE}${customerId}/`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

/**
 * Create grouped tenant/customer entry.
 */
export async function createGroup(payload) {
  return requestJson(GROUP_BASE, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
}

/**
 * Delete whole customer/group resource.
 */
export async function deleteGroup(customerId) {
  return requestOk(`${GROUP_BASE}${customerId}/`, {
    method: 'DELETE',
    headers: {
      'X-CSRFToken': getCsrfToken(),
    },
  });
}

/**
 * Delete satu baris Customer × Rack (putus relasi M2M saja).
 */
export async function deleteRow(customerId, rackId) {
  return requestOk(`${GROUP_BASE}${customerId}/rack/${rackId}/`, {
    method: 'DELETE',
    headers: {
      'X-CSRFToken': getCsrfToken(),
    },
  });
}


/** Upload customer data from CSV. */
export async function importCustomersCsv(file) {
  const form = new FormData();
  form.append('file', file);

  return requestJson('/api/customers/import-csv/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCsrfToken(),
    },
    body: form,
  });
}
