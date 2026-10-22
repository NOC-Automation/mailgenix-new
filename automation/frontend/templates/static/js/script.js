import { initLiveSync } from './liveSync.js?v=1.9.7';
import { initTabPersistence } from './tabPersistence.js?v=1.9.7';
import { initMailingListForm } from './mailingListForm.js?v=1.9.7';
import { initTenantList } from './tenantList/init.js?v=1.9.7';
import { initUsersPage } from './users/init.js?v=1.9.7';
import { initTenantWorkspace } from './tenantWorkspace.js?v=1.9.7';
import { initMailingGroupManagement } from './mailingGroupManagement.js?v=1.9.7';
import { initSequenceManagement } from './sequenceManagement.js?v=1.9.7';
import { initRemoteHands } from './remoteHands.js?v=1.9.7';
import { initChecklistOperations } from './checklistOperations.js?v=1.9.7';

function safeInit(name, fn) {
  try {
    fn();
  } catch (err) {
    console.error(`[script.js] ${name} failed:`, err);
  }
}

function boot() {
  const initializers = [
    ['initTabPersistence', initTabPersistence],
    ['initMailingListForm', initMailingListForm],
    ['initTenantWorkspace', initTenantWorkspace],
    ['initTenantList', initTenantList],
    ['initUsersPage', initUsersPage],
    ['initMailingGroupManagement', initMailingGroupManagement],
    ['initSequenceManagement', initSequenceManagement],
    ['initRemoteHands', initRemoteHands],
    ['initChecklistOperations', initChecklistOperations],
    ['initLiveSync', initLiveSync],
  ];

  for (const [name, fn] of initializers) {
    safeInit(name, fn);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true });
} else {
  boot();
}