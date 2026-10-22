// static/js/tenantList/utils.js

export function escapeHTML(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Escape regex special chars agar aman dipakai di RegExp
function escapeRegExp(str) {
  return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Highlight token pada HTML (aman): escape dulu, lalu selipkan <mark> pada match
export function highlightHTML(text, query) {
  const esc = escapeHTML(text ?? '');
  const tokens = String(query || '').trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) return esc;

  const pattern = tokens.map(escapeRegExp).join('|');
  const re = new RegExp(`(${pattern})`, 'gi');
  return esc.replace(re, '<mark>$1</mark>');
}

export function isMobile() {
  return window.matchMedia('(max-width: 767px)').matches;
}

export function debounce(fn, delay = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

export function openModal(el) {
  if (!el) return;
  el.classList.remove('hidden');
  el.classList.add('flex');

  const firstInput = el.querySelector('input, select, textarea, button');
  if (firstInput) {
    setTimeout(() => firstInput.focus(), 0);
  }
}

export function closeModal(el) {
  if (!el) return;
  el.classList.add('hidden');
  el.classList.remove('flex');
}

export function bindModalDismiss(modalEl, dataAttrValue = 'tenantEditModal') {
  if (!modalEl) return;

  // Cegah listener menumpuk
  if (modalEl.dataset.dismissBound === '1') return;
  modalEl.dataset.dismissBound = '1';

  document
    .querySelectorAll(`[data-modal-close="${dataAttrValue}"]`)
    .forEach((btn) => {
      btn.addEventListener('click', () => closeModal(modalEl));
    });

  modalEl.addEventListener('click', (e) => {
    if (e.target === modalEl) closeModal(modalEl);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modalEl.classList.contains('hidden')) {
      closeModal(modalEl);
    }
  });
}

export function getCsrfToken() {
  const name = 'csrftoken';
  const cookies = document.cookie ? document.cookie.split(';') : [];

  for (const c of cookies) {
    const x = c.trim();
    if (x.startsWith(name + '=')) {
      return decodeURIComponent(x.split('=').pop());
    }
  }

  const el = document.querySelector('[name="csrfmiddlewaretoken"]');
  return el?.value || '';
}

// --- Toast sederhana ---
export function showToast(message, type = 'success', timeout = 2500) {
  const wrap = document.getElementById('tenantToastWrap');
  if (!wrap) return;

  const el = document.createElement('div');
  el.className = `
    pointer-events-auto mx-2 rounded px-3 py-2 text-sm text-white shadow
    ${type === 'success' ? 'bg-green-600' : type === 'error' ? 'bg-rose-600' : 'bg-indigo-600'}
  `;

  // Fallback inline jika purger Tailwind menghapus kelas
  if (type === 'success') el.style.backgroundColor = el.style.backgroundColor || '#16a34a';
  if (type === 'error') el.style.backgroundColor = el.style.backgroundColor || '#dc2626';
  if (type !== 'success' && type !== 'error') {
    el.style.backgroundColor = el.style.backgroundColor || '#4f46e5';
  }

  el.textContent = message;
  wrap.appendChild(el);

  setTimeout(() => {
    el.classList.add('opacity-0', 'transition-opacity', 'duration-300');
    setTimeout(() => el.remove(), 300);
  }, timeout);
}

/**
 * Modal konfirmasi yang aman dari listener menumpuk.
 * Setiap open:
 * - reset tombol YES
 * - reset tombol close
 * - cleanup semua listener tambahan saat modal ditutup
 */
export function showConfirm(message, onYes, yesLabel = 'Ya') {
  const modal = document.getElementById('tenantConfirmModal');
  const msg = document.getElementById('tenantConfirmMessage');
  let yes = document.getElementById('tenantConfirmYes');

  if (!modal || !msg || !yes) return;

  msg.textContent = message || 'Yakin?';
  yes.textContent = yesLabel || 'Ya';

  // Reset tombol YES agar listener lama hilang
  const newYes = yes.cloneNode(true);
  yes.parentNode.replaceChild(newYes, yes);
  yes = newYes;

  // Reset tombol close agar listener lama ikut hilang
  const closeButtons = Array.from(
    document.querySelectorAll('[data-modal-close="tenantConfirmModal"]')
  ).map((btn) => {
    const replacement = btn.cloneNode(true);
    btn.parentNode.replaceChild(replacement, btn);
    return replacement;
  });

  let cleaned = false;

  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;

    modal.classList.add('hidden');
    modal.classList.remove('flex');

    modal.removeEventListener('click', onOverlayClick);
    window.removeEventListener('keydown', onEsc);
    closeButtons.forEach((btn) => btn.removeEventListener('click', onCloseClick));
  };

  const onCloseClick = () => cleanup();

  const onOverlayClick = (e) => {
    if (e.target === modal) cleanup();
  };

  const onEsc = (e) => {
    if (e.key === 'Escape') cleanup();
  };

  yes.addEventListener(
    'click',
    () => {
      cleanup();
      if (typeof onYes === 'function') onYes();
    },
    { once: true }
  );

  closeButtons.forEach((btn) => btn.addEventListener('click', onCloseClick));
  modal.addEventListener('click', onOverlayClick);
  window.addEventListener('keydown', onEsc);

  modal.classList.remove('hidden');
  modal.classList.add('flex');
}
