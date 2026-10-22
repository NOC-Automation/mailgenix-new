export function createArRow(dom, data = {}) {
  if (!dom.arList) return null;
  const tpl = document.querySelector(dom.arTemplateSel || '#arRowTemplate');
  if (!tpl?.content) return null;

  const row = tpl.content.firstElementChild.cloneNode(true);
  row.querySelector('.ar-id').value = data.id ?? '';
  row.querySelector('.ar-name').value = data.authorized_name ?? '';
  row.querySelector('.ar-email').value = data.email ?? '';
  row.querySelector('.ar-phone').value = data.phone ?? '';

  const removeBtn = row.querySelector('.ar-remove');
  removeBtn?.addEventListener('click', () => {
    const rows = dom.arList.querySelectorAll('.ar-row');
    if (rows.length <= 1) {
      row.querySelector('.ar-id').value = '';
      row.querySelector('.ar-name').value = '';
      row.querySelector('.ar-email').value = '';
      row.querySelector('.ar-phone').value = '';
      row.querySelector('.ar-name')?.focus();
      return;
    }
    row.remove();
  });

  dom.arList.appendChild(row);
  return row;
}

export function setArRows(dom, ars = []) {
  if (!dom.arList) return;
  dom.arList.innerHTML = '';
  const values = Array.isArray(ars) && ars.length ? ars : [{}];
  values.forEach((item) => createArRow(dom, item));
}

export function attachDynamicAr(dom) {
  if (!dom.arList || !dom.addArBtn) return;
  if (dom.addArBtn.dataset.bound === '1') return;
  dom.addArBtn.dataset.bound = '1';
  dom.addArBtn.addEventListener('click', () => {
    const row = createArRow(dom, {});
    row?.querySelector('.ar-name')?.focus();
  });
  if (!dom.arList.querySelector('.ar-row')) createArRow(dom, {});
}
