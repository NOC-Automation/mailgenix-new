// static/js/tabPersistence.js

// -----------------------------------------------------------------------
// CONFIG
// -----------------------------------------------------------------------
const DEFAULTS = {
  storageKey: 'homeActiveTab',
};

const CSS = {
  active: ['bg-blue-50', 'text-blue-700', 'border-blue-200'],
  hidden: ['hidden'],
  border: 'border',
};

// -----------------------------------------------------------------------
// MAIN EXPORT
// -----------------------------------------------------------------------
export function initTabPersistence({ storageKey = DEFAULTS.storageKey } = {}) {

  // -----------------------------------------------------------------------
  // DOM ELEMENTS
  // -----------------------------------------------------------------------
  const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
  const tabPanels  = Array.from(document.querySelectorAll('.tab-panel'));

  if (!tabButtons.length || !tabPanels.length) return;

  // -----------------------------------------------------------------------
  // DOUBLE-INIT GUARD
  // -----------------------------------------------------------------------
  const container = tabButtons[0].parentElement || document.body;
  if (container.dataset.tpBound === '1') return;
  container.dataset.tpBound = '1';

  // -----------------------------------------------------------------------
  // HELPERS
  // -----------------------------------------------------------------------

  /** Set an attribute only if it doesn't already exist. */
  function setAttrIfMissing(el, attr, value) {
    if (!el.getAttribute(attr)) el.setAttribute(attr, value);
  }

  /** Ensure an element has an id, generating one if needed. */
  function ensureId(el, prefix, index) {
    if (!el.id) el.id = `${prefix}-${index}`;
    return el.id;
  }

  /** Find the panel whose data-tab matches a given button. */
  function getPanelForButton(btn) {
    const name = btn.getAttribute('data-tab');
    return tabPanels.find((p) => p.getAttribute('data-tab') === name) || null;
  }

  /** Return the tab name of the first button, used as a safe fallback. */
  function getFirstTabName() {
    return tabButtons[0]?.getAttribute('data-tab') || '';
  }

  /**
   * Validate a candidate tab name.
   * Returns the candidate if it exists, otherwise falls back to the first tab.
   */
  function resolveTabName(candidate) {
    if (!candidate) return getFirstTabName();
    const exists = tabButtons.some((btn) => btn.getAttribute('data-tab') === candidate);
    return exists ? candidate : getFirstTabName();
  }

  /** Read from localStorage without throwing. */
  function readStorage() {
    try { return localStorage.getItem(storageKey); } catch (_) { return null; }
  }

  /** Write to localStorage without throwing. */
  function writeStorage(value) {
    try { localStorage.setItem(storageKey, value); } catch (_) {}
  }

  // -----------------------------------------------------------------------
  // ARIA SETUP
  // -----------------------------------------------------------------------
  setAttrIfMissing(container, 'role', 'tablist');

  tabButtons.forEach((btn, i) => {
    setAttrIfMissing(btn, 'role', 'tab');
    setAttrIfMissing(btn, 'tabindex', '-1');

    const panel = getPanelForButton(btn);
    if (!panel) return;

    const panelId = ensureId(panel, 'tp-panel', i);
    const btnId   = ensureId(btn,   'tp-tab',   i);

    btn.setAttribute('aria-controls', panelId);
    panel.setAttribute('aria-labelledby', btnId);
    setAttrIfMissing(panel, 'role', 'tabpanel');
    setAttrIfMissing(panel, 'tabindex', '0');

    deactivatePanel(panel);
  });

  // -----------------------------------------------------------------------
  // VISUAL STATE SETTERS
  // -----------------------------------------------------------------------

  function activateButton(btn) {
    btn.setAttribute('aria-selected', 'true');
    btn.setAttribute('tabindex', '0');
    btn.classList.add(...CSS.active);
    btn.classList.add(CSS.border);
  }

  function deactivateButton(btn) {
    btn.setAttribute('aria-selected', 'false');
    btn.setAttribute('tabindex', '-1');
    btn.classList.remove(...CSS.active);
  }

  function activatePanel(panel) {
    panel.classList.remove(...CSS.hidden);
    panel.hidden = false;
    panel.setAttribute('aria-hidden', 'false');
  }

  function deactivatePanel(panel) {
    panel.classList.add(...CSS.hidden);
    panel.hidden = true;
    panel.setAttribute('aria-hidden', 'true');
  }

  // -----------------------------------------------------------------------
  // CORE: ACTIVATE A TAB
  // -----------------------------------------------------------------------

  /**
   * Show the tab matching tabName, hide all others,
   * persist the choice, and optionally move focus.
   */
  function activateTab(tabName, { focus = false } = {}) {
    const resolved = resolveTabName(tabName);

    tabButtons.forEach((btn) => {
      const isActive = btn.getAttribute('data-tab') === resolved;
      isActive ? activateButton(btn) : deactivateButton(btn);
    });

    tabPanels.forEach((panel) => {
      const isActive = panel.getAttribute('data-tab') === resolved;
      isActive ? activatePanel(panel) : deactivatePanel(panel);
    });

    writeStorage(resolved);

    if (focus) {
      tabButtons.find((btn) => btn.getAttribute('data-tab') === resolved)?.focus();
    }
  }

  // -----------------------------------------------------------------------
  // DETERMINE INITIAL TAB
  // -----------------------------------------------------------------------

  function resolveInitialTab() {
    const persisted = readStorage();
    if (persisted) return persisted;

    const preset = tabButtons.find((btn) => btn.dataset.active === 'true');
    return preset ? preset.getAttribute('data-tab') : getFirstTabName();
  }

  activateTab(resolveInitialTab());

  // -----------------------------------------------------------------------
  // CLICK HANDLERS
  // -----------------------------------------------------------------------

  tabButtons.forEach((btn) => {
    if (btn.dataset.tpBound === '1') return;
    btn.dataset.tpBound = '1';

    btn.addEventListener('click', () => {
      activateTab(btn.getAttribute('data-tab'), { focus: true });
    });
  });

  // -----------------------------------------------------------------------
  // KEYBOARD NAVIGATION (ARIA tabs pattern)
  // -----------------------------------------------------------------------

  if (container.dataset.tpKbBound === '1') return;
  container.dataset.tpKbBound = '1';

  container.addEventListener('keydown', (e) => {
    const currentIndex = tabButtons.findIndex(
      (btn) => btn.getAttribute('aria-selected') === 'true'
    );
    if (currentIndex < 0) return;

    const last = tabButtons.length - 1;

    const keyActions = {
      ArrowRight: () => tabButtons[(currentIndex + 1) % tabButtons.length],
      ArrowDown:  () => tabButtons[(currentIndex + 1) % tabButtons.length],
      ArrowLeft:  () => tabButtons[(currentIndex - 1 + tabButtons.length) % tabButtons.length],
      ArrowUp:    () => tabButtons[(currentIndex - 1 + tabButtons.length) % tabButtons.length],
      Home:       () => tabButtons[0],
      End:        () => tabButtons[last],
    };

    const getTarget = keyActions[e.key];
    if (!getTarget) return;

    e.preventDefault();
    activateTab(getTarget().getAttribute('data-tab'), { focus: true });
  });
}
