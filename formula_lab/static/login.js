const signIn = document.getElementById('google-sign-in');
const status = document.getElementById('login-status');
const query = new URLSearchParams(location.search);
signIn.href = `/auth/google/login?${new URLSearchParams({next: query.get('next') || '/'})}`;
signIn.addEventListener('click', event => {if (signIn.getAttribute('aria-disabled') === 'true') event.preventDefault();});
fetch('/auth/config', {cache: 'no-store'}).then(async response => {
  if (!response.ok) throw new Error();
  const config = await response.json();
  if (!config.configured) {
    status.textContent = 'Google sign-in is not configured yet. Please try again later.';
    return;
  }
  signIn.removeAttribute('aria-disabled'); signIn.removeAttribute('tabindex');
  if (query.get('error')) {
    status.className = 'error';
    status.textContent = 'Sign-in could not be completed. Please try again.';
  } else {status.hidden = true;}
}).catch(() => {status.textContent = 'Sign-in is temporarily unavailable. Please reload to try again.';});
