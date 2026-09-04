(() => {
  const cards = [...document.querySelectorAll('.review-card')].filter(
    (card) => card.querySelector('.decision-form')
  );
  if (!cards.length) return;
  let activeIndex = 0;

  function isTyping() {
    const tag = document.activeElement && document.activeElement.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
  }

  function focusCard(index) {
    if (index < 0 || index >= cards.length) return;
    activeIndex = index;
    const card = cards[activeIndex];
    card.scrollIntoView({ block: 'center', behavior: 'smooth' });
    const textarea = card.querySelector('.decision-form textarea[name="reason"]');
    if (textarea) textarea.focus({ preventScroll: true });
  }

  function currentForm() {
    const card = cards[activeIndex];
    return card ? card.querySelector('.decision-form') : null;
  }

  function submitDecision(value) {
    const form = currentForm();
    if (!form) return;
    const button = form.querySelector(`button[name="decision"][value="${value}"]`);
    if (!button) return;
    // requestSubmit keeps native required-field validation (reason, confirm checkbox);
    // it never bypasses the audit trail, it just avoids reaching for the mouse.
    if (form.requestSubmit) form.requestSubmit(button);
    else button.click();
  }

  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey && event.key === 'Enter') {
      event.preventDefault();
      submitDecision(event.shiftKey ? 'reject' : 'approve');
      return;
    }
    if (isTyping()) return;
    if (event.key === 'j' || event.key === 'ArrowDown') {
      event.preventDefault();
      focusCard(activeIndex + 1);
    } else if (event.key === 'k' || event.key === 'ArrowUp') {
      event.preventDefault();
      focusCard(activeIndex - 1);
    }
  });
})();
