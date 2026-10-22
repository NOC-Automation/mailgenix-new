// static/js/tenantList/tenantAdd/mailingList.js

export function attachMailingListToggle(dom) {
  if (!dom.btnAddMailingList || !dom.mailingListContainer) return;
  if (dom.btnAddMailingList.dataset.bound === '1') return;
  dom.btnAddMailingList.dataset.bound = '1';

  dom.btnAddMailingList.addEventListener('click', () => {
    dom.mailingListContainer.classList.remove('hidden');
    dom.btnAddMailingList.classList.add('hidden');
  });
}

export function prefillMailingList(dom, mailingList) {
  let vals = [];

  if (Array.isArray(mailingList)) {
    vals = mailingList.map((v) => (v || '').trim()).filter(Boolean);
  } else if (typeof mailingList === 'string' && mailingList.trim()) {
    vals = mailingList
      .split(';')
      .map((v) => v.trim())
      .filter(Boolean);
  }

  if (!dom.mailingListInput) return;

  if (!vals.length) {
    dom.mailingListInput.value = '';
    return;
  }

  if (dom.mailingListContainer) {
    dom.mailingListContainer.classList.remove('hidden');
    dom.mailingListContainer.style.display = '';
  }

  if (dom.btnAddMailingList) {
    dom.btnAddMailingList.classList.add('hidden');
    dom.btnAddMailingList.style.display = 'none';
  }

  dom.mailingListInput.value = vals.join('; ');
}
