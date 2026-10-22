// static/js/tenantList/actions.js
// Legacy fallback actions for Tenant List.
// Modern flow utama sekarang ditangani oleh:
// - renderers.js  -> render tombol modern
// - events.js     -> handle group-edit / row-delete
// File ini dipertahankan sementara agar tidak mem-break modal/action lama.

import { openModal, closeModal, showConfirm, showToast } from './utils.js';

let savingLegacyModal = false;

function setModalUi(dom, { title, saveLabel, savingLabel }) {
  if (dom.tenantModalTitle) {
    dom.tenantModalTitle.textContent = title;
  }

  if (dom.saveBtn) {
    dom.saveBtn.textContent = saveLabel;
    dom.saveBtn.dataset.defaultLabel = saveLabel;
    dom.saveBtn.dataset.savingLabel = savingLabel || 'Saving...';
  }
}

function normalizeId(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function findRowForId(list, rawId) {
  const id = normalizeId(rawId);
  if (id == null) return null;

  for (const row of Array.isArray(list) ? list : []) {
    if (!row || typeof row !== 'object') continue;

    // Legacy single row
    if (normalizeId(row.id) === id) {
      return { row, index: 0, grouped: false };
    }

    // Grouped row
    if (Array.isArray(row.id_list)) {
      const idx = row.id_list.findIndex((x) => normalizeId(x) === id);
      if (idx !== -1) {
        return { row, index: idx, grouped: true };
      }
    }
  }

  return null;
}

function setSaving(dom, isSaving) {
  if (!dom.saveBtn) return;

  dom.saveBtn.disabled = isSaving;

  const defaultLabel = dom.saveBtn.dataset.defaultLabel || 'Save';
  const savingLabel = dom.saveBtn.dataset.savingLabel || 'Saving...';

  dom.saveBtn.textContent = isSaving ? savingLabel : defaultLabel;
}

export function openEditModal(store, dom, id) {
  const list = Array.isArray(store.state.rows) ? store.state.rows : [];
  const match = findRowForId(list, id);
  if (!match) return;

  store.state.editingId = normalizeId(id);

  const { row, index, grouped } = match;

  const val = (key, fallbackKey) => {
    if (grouped) {
      const arr = row[`${key}_list`];
      if (Array.isArray(arr)) return arr[index] ?? '';
      return row[fallbackKey] ?? '';
    }
    return row[key] ?? '';
  };

  if (dom.editRackLocation) dom.editRackLocation.value = row.rack_location ?? '';
  if (dom.editCustomerName) dom.editCustomerName.value = row.customer_name ?? '';
  if (dom.editAuthorizedPerson) dom.editAuthorizedPerson.value = val('authorized_person', 'authorized_person');
  if (dom.editEmail) dom.editEmail.value = val('email', 'email');
  if (dom.editPhone) dom.editPhone.value = val('phone', 'phone');
  if (dom.editDate) dom.editDate.value = val('date', 'date');
  if (dom.editValidity) dom.editValidity.value = val('validity', 'validity');

  setModalUi(dom, {
    title: 'Edit Tenant',
    saveLabel: 'Save',
    savingLabel: 'Saving...',
  });

  openModal(dom.editModal);
}

export function validateEditForm(dom) {
  if (!dom.editForm?.checkValidity?.()) {
    dom.editForm?.reportValidity?.();
    return false;
  }

  const email = dom.editEmail?.value?.trim?.() || '';
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    if (dom.editEmail?.setCustomValidity) {
      dom.editEmail.setCustomValidity('Format email tidak valid');
      dom.editForm?.reportValidity?.();
      dom.editEmail.setCustomValidity('');
    }
    return false;
  }

  return true;
}

export function readFormData(dom) {
  return {
    rack_location: dom.editRackLocation?.value?.trim?.() || '',
    customer_name: dom.editCustomerName?.value?.trim?.() || '',
    authorized_person: dom.editAuthorizedPerson?.value?.trim?.() || '',
    email: dom.editEmail?.value?.trim?.() || '',
    phone: dom.editPhone?.value?.trim?.() || '',
    date: dom.editDate?.value || null,
    validity: dom.editValidity?.value || null,
  };
}

/**
 * Legacy modal save flow.
 * Dipertahankan sementara agar tidak mem-break halaman lama yang masih
 * menyertakan modal edit tenant.
 */
export async function handleSaveClick(store, dom, api, render) {
  if (!validateEditForm(dom)) {
    showToast('Harap lengkapi form edit.', 'error');
    return;
  }

  if (savingLegacyModal) return;

  const payload = readFormData(dom);
  const id = normalizeId(store.state.editingId);
  const isCreate = id == null;

  const yesLabel = isCreate ? 'Tambah' : 'Simpan';
  const msg = isCreate
    ? `Yakin ingin menambahkan customer baru: ${payload.customer_name || '(tanpa nama)'}?`
    : `Yakin ingin menyimpan perubahan untuk: ${payload.customer_name || '(tanpa nama)'}?`;

  showConfirm(
    msg,
    async () => {
      savingLegacyModal = true;

      try {
        setSaving(dom, true);

        if (!store.state.serverMode) {
          showToast('Client mode tidak diaktifkan.', 'error');
          return;
        }

        if (isCreate) {
          // Legacy endpoint — dipertahankan sementara
          await api.createTenant(payload);
        } else {
          // Legacy endpoint — dipertahankan sementara
          await api.updateTenant(id, payload);
        }

        await api.loadFromServer(store);

        store.state.editingId = null;
        closeModal(dom.editModal);
        render();

        showToast(
          isCreate
            ? 'Customer berhasil ditambahkan.'
            : 'Perubahan berhasil disimpan.',
          'success'
        );
      } catch (err) {
        console.error('[TenantList][LegacySave] failed:', err);
        showToast(
          isCreate
            ? 'Gagal menambah data. Coba lagi.'
            : 'Gagal menyimpan perubahan. Coba lagi.',
          'error'
        );
      } finally {
        setSaving(dom, false);
        savingLegacyModal = false;
      }
    },
    yesLabel
  );
}

/**
 * Legacy delete flow.
 * Dipertahankan sementara kalau masih ada tombol delete lama berbasis id tunggal.
 */
export async function confirmDelete(store, id, api, render) {
  const list = Array.isArray(store.state.rows) ? store.state.rows : [];
  const match = findRowForId(list, id);
  if (!match) return;

  const { row } = match;
  const message = `Yakin ingin menghapus data tenant: ${row.customer_name} (${row.rack_location})?`;

  showConfirm(message, async () => {
    try {
      await api.deleteTenant(id); // legacy endpoint
    } catch (err) {
      console.error('[TenantList][LegacyDelete] failed:', err);
      showToast('Gagal menghapus data. Coba lagi.', 'error');
      return;
    }

    try {
      await api.loadFromServer(store);
    } catch (_) {
      // fallback diam; render local tetap dipanggil
    }

    render();
    showToast('Tenant berhasil dihapus.', 'success');
  });
}

/**
 * Legacy delegated action fallback.
 * Modern actions utama ditangani di events.js:
 * - group-edit
 * - row-delete
 */
export function handleActionClick(store, e, dom, api, render) {
  const btn = e.target.closest('button[data-action][data-id]');
  if (!btn) return;

  const action = btn.getAttribute('data-action');
  const id = normalizeId(btn.getAttribute('data-id'));
  if (id == null) return;

  if (action === 'edit') {
    openEditModal(store, dom, id);
    return;
  }

  if (action === 'delete') {
    confirmDelete(store, id, api, render);
  }
}
