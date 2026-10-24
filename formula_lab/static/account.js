/* Shared identity and authenticated requests for the library and workspace. */
window.MathPDFSession = (() => {
  let user, redirecting = false;
  function signIn() {
    if (!redirecting) {
      redirecting = true;
      location.assign(`/login?${new URLSearchParams({next: location.pathname + location.search})}`);
    }
    throw new Error('Your session has expired. Sign in to continue.');
  }
  async function request(path, options = {}) {
    const headers = {...options.headers};
    if (user) headers['X-MathPDF-User'] = user.id;
    const response = await fetch(path, {...options, headers, credentials: 'same-origin', cache: 'no-store'});
    if (response.status === 401) signIn();
    if (response.headers.get('X-MathPDF-Account-Changed') === '1') {
      location.assign('/'); throw new Error('The active account has changed. Reopening your library.');
    }
    return response;
  }
  async function api(path, options = {}) {
    const headers = options.body instanceof FormData ? {} : {'Content-Type': 'application/json'};
    const response = await request(path, {...options, headers: {...headers, ...options.headers}});
    let data;
    try {data = await response.json();} catch {throw new Error('The server returned an unreadable response.');}
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.');
    return data;
  }
  const ready = api('/api/me').then(identity => {
    user = identity;
    const container = document.getElementById('account');
    if (container) {
      const menu = document.createElement('details'); menu.className = 'account-menu';
      const summary = document.createElement('summary'); summary.setAttribute('aria-label', `Account: ${user.email}`);
      const avatar = document.createElement('span'); avatar.className = 'account-avatar'; avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = user.name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => [...part][0]).join('').toUpperCase();
      const label = document.createElement('span'); label.className = 'account-label'; label.textContent = user.name;
      summary.append(avatar, label);
      const panel = document.createElement('div'); panel.className = 'account-panel';
      const name = document.createElement('strong'); name.textContent = user.name;
      const email = document.createElement('span'); email.className = 'account-email'; email.textContent = user.email;
      const form = document.createElement('form'); form.method = 'post'; form.action = '/auth/logout';
      const logout = document.createElement('button'); logout.type = 'submit'; logout.className = 'secondary'; logout.textContent = 'Sign out';
      form.append(logout); panel.append(name, email, form); menu.append(summary, panel); container.replaceChildren(menu);
      document.addEventListener('click', event => {if (!menu.contains(event.target)) menu.open = false;});
      document.addEventListener('keydown', event => {if (event.key === 'Escape') {menu.open = false; summary.focus();}});
    }
    return user;
  });
  // Consumers display request failures in their own status region.
  ready.catch(() => {});
  addEventListener('pageshow', event => {if (event.persisted) location.reload();});
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && user) api('/api/me').catch(() => {});
  });
  return {api, request, ready, get user() {return user;}};
})();
