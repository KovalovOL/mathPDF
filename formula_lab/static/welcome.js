/* One-time account welcome. Native dialog supplies focus trapping and Escape dismissal. */
export async function showWelcome({api}) {
  if (document.querySelector('dialog[open]')) return;
  const dialog = document.createElement('dialog');
  dialog.className = 'welcome-dialog';
  dialog.setAttribute('aria-labelledby', 'welcome-title');
  dialog.setAttribute('aria-describedby', 'welcome-intro');
  dialog.innerHTML = `<div class="dialog-header"><h2 id="welcome-title">Welcome to MathPDF!</h2><button type="button" class="icon-button" aria-label="Close welcome">&times;</button></div>
    <div class="dialog-body"><p id="welcome-intro">Here's what you can do:</p>
    <ul class="welcome-features">
      <li><strong>Annotate your PDFs</strong><span>Highlight, draw, and add notes directly to your documents.</span></li>
      <li><strong>Generate flashcards</strong><span>Turn your study materials into flashcards.</span></li>
      <li><strong>Test your knowledge</strong><span>Generate practice questions based on your PDFs.</span></li>
    </ul></div><div class="dialog-footer"><button type="button" autofocus>Start learning</button></div>`;
  // Wait for confirmation before displaying; failure must never block the application.
  const receipt = await api('/api/welcome/claim', {method: 'POST'});
  if (!receipt.show || document.querySelector('dialog[open]')) return;
  const previousFocus = document.activeElement;
  dialog.querySelectorAll('button').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', event => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  });
  dialog.addEventListener('close', () => {dialog.remove();if(previousFocus?.isConnected)previousFocus.focus();}, {once: true});
  document.body.append(dialog);
  dialog.showModal();
}
