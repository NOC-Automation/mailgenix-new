// static/js/tenantList/tenantAdd/autocomplete/shared.js

export function debounce(fn, wait = 250) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

export async function fetchJson(url) {
  const res = await fetch(url, {
    method: 'GET',
    credentials: 'same-origin',
  });

  if (!res.ok) {
    let msg = 'Request gagal.';
    try {
      const j = await res.json();
      msg = j?.detail || msg;
    } catch (_) {}
    throw new Error(msg);
  }

  return res.json();
}

export function openSuggest(box) {
  if (!box) return;
  box.classList.remove('hidden');
}

export function closeSuggest(box) {
  if (!box) return;
  box.classList.add('hidden');
}

export function clearSuggest(listEl, box) {
  if (listEl) listEl.innerHTML = '';
  closeSuggest(box);
}

export function renderSuggest(listEl, box, items, onPick, activeIndex = -1) {
  if (!listEl || !box) return;
  listEl.innerHTML = '';

  if (!items || items.length === 0) {
    closeSuggest(box);
    return;
  }

  const MAX_VISIBLE_SUGGESTIONS = 5;
  const SUGGESTION_ROW_PX = 40;
  const maxH = MAX_VISIBLE_SUGGESTIONS * SUGGESTION_ROW_PX;

  if (items.length > MAX_VISIBLE_SUGGESTIONS) {
    listEl.style.maxHeight = `${maxH}px`;
    listEl.style.overflowY = 'auto';
  } else {
    listEl.style.maxHeight = '';
    listEl.style.overflowY = '';
  }

  items.forEach((item, idx) => {
    const li = document.createElement('li');
    const isActive = idx === activeIndex;

    li.dataset.index = String(idx);

    li.className = [
      'px-3 py-2 cursor-pointer',
      'text-slate-700',
      'hover:bg-slate-100',
      isActive ? 'bg-blue-600 text-white font-medium' : '',
    ].join(' ').trim();

    if (isActive) {
      li.style.backgroundColor = '#2563eb';
      li.style.color = '#ffffff';
      li.style.fontWeight = '600';
    } else {
      li.style.backgroundColor = '';
      li.style.color = '';
      li.style.fontWeight = '';
    }

    li.textContent = item.name;

    li.addEventListener('mousedown', (e) => {
      e.preventDefault();
      onPick(item);
    });

    listEl.appendChild(li);
  });

  openSuggest(box);

  if (activeIndex >= 0 && listEl.children[activeIndex]) {
    try {
      listEl.children[activeIndex].scrollIntoView({ block: 'nearest' });
    } catch (_) {}
  }
}

export function applyActiveToList(listEl, activeIndex) {
  if (!listEl) return;

  const children = Array.from(listEl.children);
  children.forEach((li, idx) => {
    const isActive = idx === activeIndex;

    li.classList.toggle('bg-blue-600', isActive);
    li.classList.toggle('text-white', isActive);
    li.classList.toggle('font-medium', isActive);

    if (!isActive) {
      li.classList.remove('text-slate-900');
    }

    if (isActive) {
      li.style.backgroundColor = '#2563eb';
      li.style.color = '#ffffff';
      li.style.fontWeight = '600';
    } else {
      li.style.backgroundColor = '';
      li.style.color = '';
      li.style.fontWeight = '';
    }
  });

  const activeEl = children[activeIndex];
  if (activeEl) {
    try {
      activeEl.scrollIntoView({ block: 'nearest' });
    } catch (_) {}
  }
}

export function bindSuggestHover(listEl, getActive, setActive) {
  if (!listEl) return;
  if (listEl.dataset.hoverBound === '1') return;
  listEl.dataset.hoverBound = '1';

  listEl.addEventListener('mousemove', (e) => {
    const li = e.target.closest('li');
    if (!li || !listEl.contains(li)) return;

    const idx = Number(li.dataset.index);
    if (Number.isNaN(idx)) return;

    if (idx !== getActive()) {
      setActive(idx);
      applyActiveToList(listEl, idx);
    }
  });
}

export function bindSuggestOutsideClose(inputEl, box) {
  if (!inputEl || !box) return;
  if (box.dataset.outsideBound === '1') return;
  box.dataset.outsideBound = '1';

  document.addEventListener('click', (ev) => {
    if (!box.contains(ev.target) && ev.target !== inputEl) {
      closeSuggest(box);
    }
  });
}

export function bindSuggestKeyboard({
  inputEl,
  listEl,
  box,
  getItems,
  getActive,
  setActive,
  onPick,
  onClear,
}) {
  if (!inputEl || !listEl || !box) return;
  if (inputEl.dataset.kbdBound === '1') return;
  inputEl.dataset.kbdBound = '1';

  inputEl.addEventListener('keydown', (e) => {
    const items = getItems();
    if (!items || items.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = (getActive() + 1) % items.length;
      setActive(next);
      applyActiveToList(listEl, next);
      openSuggest(box);
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = (getActive() - 1 + items.length) % items.length;
      setActive(prev);
      applyActiveToList(listEl, prev);
      openSuggest(box);
      return;
    }

    if (e.key === 'Enter') {
      const active = getActive();
      if (active >= 0 && items[active]) {
        e.preventDefault();
        onPick(items[active]);
      }
      return;
    }

    if (e.key === 'Escape') {
      e.preventDefault();
      onClear();
    }
  });
}

export function normalizeText(value) {
  return (value || '').trim();
}

export function ensureSelectValue(selectEl, id, text) {
  if (!selectEl || id == null || id === '') return false;

  const value = String(id);

  if (![...selectEl.options].some((opt) => opt.value === value)) {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = text || value;
    selectEl.appendChild(opt);
  }

  selectEl.value = value;
  return true;
}
