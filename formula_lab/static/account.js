/* Shared identity and authenticated requests for the library and workspace. */
window.MathPDFSession = (() => {
  let user, redirecting = false, leaveGuard, cancelLeave;
  let diagnosticCount = 0;
  const reporter=import('/static/reports.js').then(module=>module.initialize({getUser:()=>user})).catch(()=>null);
  let contextProvider=()=>({});
  reporter.then(r=>r?.setContextProvider(()=>contextProvider()));
  const clientBuild = document.querySelector('meta[name="mathpdf-build"]')?.content || null;
  const newReference = () => crypto.randomUUID().replaceAll('-', '');
  function routeLabel(path) {
    try {
      const pathname = new URL(path, location.origin).pathname;
      if (pathname.startsWith('/api/')) {
        const label = pathname.replace(/[a-f0-9]{32}|[a-f0-9-]{36}/g, '{id}');
        return /^\/api\/[A-Za-z0-9_/{}/.-]{1,160}$/.test(label) ? label : '/api/other';
      }
      return ['/', '/workspace', '/login'].includes(pathname) ? pathname : '/other';
    } catch {return '/other';}
  }
  function reportFailure(event, path, method, reference, response, receivedBytes) {
    const echoed = response?.headers.get('X-MathPDF-Request-ID');
    const build = response?.headers.get('X-MathPDF-Build');
    const mime = (response?.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
    const length = Number(response?.headers.get('Content-Length') ?? NaN);
    const report = {event, request_id: /^[a-f0-9]{32}$/.test(echoed || '') ? echoed : reference,
      route: routeLabel(path), method: (method || 'GET').toUpperCase(), status: response?.status || null,
      received_bytes: receivedBytes, expected_bytes: Number.isSafeInteger(length) && length >= 0 && length <= 104857600 ? length : null,
      content_type: /^[A-Za-z0-9.+/-]{0,80}$/.test(mime) ? mime : '', redirected: !!response?.redirected,
      response_route: routeLabel(response?.url || '/other'),
      server_build: /^[a-f0-9]{12}$/.test(build || '') ? build : null,
      client_build: /^[a-f0-9]{12}$/.test(clientBuild || '') ? clientBuild : null};
    console.error('mathPDF API failure', report);
    if (user && diagnosticCount++ < 10) {
      // Do not use api() here: a failing diagnostic request must never recurse.
      fetch('/api/client-errors', {method: 'POST', credentials: 'same-origin', cache: 'no-store', keepalive: true,
        headers: {'Content-Type': 'application/json', 'X-MathPDF-User': user.id, 'X-MathPDF-Request-ID': newReference()},
        body: JSON.stringify(report)}).catch(() => {});
    }
    return report.request_id;
  }
  function signIn() {
    if (!redirecting) {
      redirecting = true;
      location.assign(`/login?${new URLSearchParams({next: location.pathname + location.search})}`);
    }
    const error = new Error('Your session has expired. Sign in to continue.'); error.status = 401; throw error;
  }
  async function request(path, options = {}) {
    const headers = {...options.headers};
    if (!headers['X-MathPDF-Request-ID']) headers['X-MathPDF-Request-ID'] = newReference();
    if (user) headers['X-MathPDF-User'] = user.id;
    const response = await fetch(path, {...options, headers, credentials: 'same-origin', cache: 'no-store'});
    let diagnosticResponse;try{if(path.startsWith('/api/')&&(response.status>=400||(response.headers.get('content-type')||'').includes('json')))diagnosticResponse=response.clone();}catch{}
    if(diagnosticResponse)reporter.then(r=>r?.observe(path,options,diagnosticResponse)).catch(()=>{});
    if (response.status === 401) signIn();
    if (response.headers.get('X-MathPDF-Account-Changed') === '1') {
      location.assign('/'); throw new Error('The active account has changed. Reopening your library.');
    }
    return response;
  }
  async function api(path, options = {}) {
    const {timeoutMs = options.body instanceof FormData ? 180000 : 30000, signal, ...settings} = options;
    const controller = new AbortController();
    const cancelled = () => controller.abort(signal.reason);
    if (signal?.aborted) cancelled(); else signal?.addEventListener('abort', cancelled, {once: true});
    const timer = setTimeout(() => controller.abort(new Error('The server did not respond in time. Please try again.')), timeoutMs);
    const reference = newReference();
    let response, reported = false, receivedBytes = null;
    function failure(message, event) {
      reported = true;
      const id = reportFailure(event, path, settings.method, reference, response, receivedBytes);
      const error = new Error(`${message} Reference: ${id}`); error.status = response?.status; return error;
    }
    try {
      const headers = settings.body instanceof FormData ? {} : {'Content-Type': 'application/json'};
      response = await request(path, {...settings, signal: controller.signal,
        headers: {...headers, ...settings.headers, 'X-MathPDF-Request-ID': reference}});
      if (response.status === 204) return null;
      const mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      if (mime !== 'application/json' && !mime.endsWith('+json')) {
        const error = failure(`Expected JSON but received ${mime || 'an unknown content type'} (HTTP ${response.status}). Reload this page.`, 'unexpected_content_type');
        if (response.redirected && routeLabel(response.url) === '/login') signIn();
        throw error;
      }
      let data;
      try {
        const text = await response.text();
        receivedBytes = new TextEncoder().encode(text).length;
        data = JSON.parse(text);
      } catch {
        if (controller.signal.aborted) throw controller.signal.reason;
        throw failure(`The API response contains invalid or empty JSON (HTTP ${response.status}, ${mime}).`, 'invalid_json');
      }
      if (!response.ok) throw failure(`${typeof data?.detail === 'string' ? data.detail : 'The request could not be completed'} (HTTP ${response.status}).`, 'http_error');
      return data;
    } catch (error) {
      if (controller.signal.aborted) {
        if (controller.signal.reason?.name === 'AbortError') throw controller.signal.reason;
        throw reported ? error : failure(controller.signal.reason?.message || 'The request timed out.', 'timeout');
      }
      if (error instanceof TypeError && !reported) throw failure('Could not reach the server. Check your connection and try again.', 'network_error');
      throw error;
    } finally {
      clearTimeout(timer); signal?.removeEventListener('abort', cancelled);
    }
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
      const logoutError=document.createElement('p');logoutError.className='error';logoutError.hidden=true;logoutError.setAttribute('role','alert');
      form.addEventListener('submit', async event => {
        event.preventDefault(); logout.disabled = true;logoutError.hidden=true;
        let logoutTimer;
        try {
          if (leaveGuard && !await leaveGuard()) return;
          const controller=new AbortController();logoutTimer=setTimeout(()=>controller.abort(),15000);
          const response=await request('/auth/logout',{method:'POST',signal:controller.signal});
          if(!response.ok)throw new Error('Could not sign out. Please try again.');
          try {await (await import('/static/visual-cache.js')).clearVisualCache(user.id);} catch {}
          location.assign('/login');
        } catch(error) {
          cancelLeave?.();logoutError.textContent=error.name==='AbortError'?'Sign-out timed out. Please try again.':error.message;logoutError.hidden=false;menu.open=true;
        } finally {clearTimeout(logoutTimer);logout.disabled=false;}
      });
      form.append(logout,logoutError); panel.append(name, email);
      const role=document.createElement('span');role.className='account-role';role.textContent=(user.role||'free').replace(/^./,c=>c.toUpperCase());panel.append(role);
      if(['admin','owner'].includes(user.role)){const admin=document.createElement('a');admin.href='/admin';admin.textContent='Administration';panel.append(admin);}
      reporter.then(r=>{if(r){const feedback=r.button();feedback.addEventListener('click',()=>menu.open=false);panel.insertBefore(feedback,form);}});
      panel.append(form); menu.append(summary, panel); container.replaceChildren(menu);
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
  return {api, request, ready, setContextProvider:provider=>contextProvider=provider, setLeaveGuard:(guard,cancel)=>{leaveGuard=guard;cancelLeave=cancel;}, get user() {return user;}};
})();
