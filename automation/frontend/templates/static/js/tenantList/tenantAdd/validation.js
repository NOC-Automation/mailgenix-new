// static/js/tenantList/tenantAdd/validation.js

export function markRackInvalid(dom, msg = 'Silakan pilih Rack.') {
  const el = dom.rackInput || dom.rackLocation;
  if (!el) return;

  el.classList.add('border-rose-500', 'ring-1', 'ring-rose-500');
  if (typeof el.setCustomValidity === 'function') {
    el.setCustomValidity(msg);
  }

  try {
    el.focus({ preventScroll: false });
  } catch (_) {}

  try {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (_) {}

  if (!el.dataset._rackBound) {
    el.dataset._rackBound = '1';
    el.addEventListener('change', () => {
      el.classList.remove('border-rose-500', 'ring-rose-500', 'ring-1');
      if (typeof el.setCustomValidity === 'function') {
        el.setCustomValidity('');
      }
      const help = document.getElementById('addRackHelp');
      if (help) help.classList.add('hidden');
    });
  }

  const help = document.getElementById('addRackHelp');
  if (help) {
    help.textContent = msg;
    help.classList.remove('hidden');
  }
}

export function markCustomerInvalid(dom, msg = 'Silakan isi Customer Name.') {
  const el = dom.customerName;
  if (!el) return;

  el.classList.add('border-rose-500', 'ring-1', 'ring-rose-500');
  if (typeof el.setCustomValidity === 'function') {
    el.setCustomValidity(msg);
  }

  try {
    el.focus({ preventScroll: false });
  } catch (_) {}

  try {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (_) {}

  if (!el.dataset._custBound) {
    el.dataset._custBound = '1';

    const clear = () => {
      el.classList.remove('border-rose-500', 'ring-rose-500', 'ring-1');
      if (typeof el.setCustomValidity === 'function') {
        el.setCustomValidity('');
      }
      const help = document.getElementById('addCustomerNameHelp');
      if (help) help.classList.add('hidden');
    };

    el.addEventListener('input', clear);
    el.addEventListener('change', clear);
  }

  const help = document.getElementById('addCustomerNameHelp');
  if (help) {
    help.textContent = msg;
    help.classList.remove('hidden');
  }
}

export function validateUniqueAuthorizedEmails(ars) {
  if (!Array.isArray(ars)) {
    return { ok: false, msg: 'Data AR tidak valid.' };
  }

  const filled = ars.filter((a) => (a.email || '').trim() !== '');

  if (filled.length === 0) {
    return {
      ok: false,
      msg: 'Minimal 1 Authorized Person harus memiliki email.',
    };
  }

  const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  for (const a of filled) {
    const email = a.email.trim();
    if (!emailRe.test(email)) {
      return { ok: false, msg: `Format email tidak valid: ${email}` };
    }
  }

  const lower = filled.map((a) => a.email.trim().toLowerCase());
  if (new Set(lower).size !== lower.length) {
    return { ok: false, msg: 'Email AR tidak boleh duplikat.' };
  }

  return { ok: true };
}

export function validatePayloadBeforeSubmit(payload, dom) {
  if (!payload.customer_name) {
    const msg = 'Silakan isi Customer Name.';
    markCustomerInvalid(dom, msg);
    throw new Error(msg);
  }

  if (Array.isArray(payload.mailing_list) && payload.mailing_list.length) {
    const invalid = payload.mailing_list.filter(
      (v) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
    );
    if (invalid.length) {
      throw new Error(`Format mailing list tidak valid: ${invalid.join(', ')}`);
    }
  }

  const result = validateUniqueAuthorizedEmails(payload.ars || []);
  if (!result.ok) {
    throw new Error(result.msg);
  }

  return true;
}
