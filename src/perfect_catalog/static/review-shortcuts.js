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
    cards[activeIndex].scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  function decisionForm(value) {
    const card = cards[activeIndex];
    return card ? card.querySelector(`.decision-form[data-decision="${value}"]`) : null;
  }

  function submitDecision(value) {
    const form = decisionForm(value);
    if (!form) return;
    if (value === 'reject') {
      // El rechazo vive detrás de un <details> colapsado (aprobar es el camino rápido,
      // sin motivo); ábrelo para que el textarea requerido sea visible y foqueable.
      const details = form.closest('details');
      if (details) details.open = true;
    }
    // requestSubmit keeps native required-field validation (reason on reject, confirm
    // checkbox always); it never bypasses the audit trail, it just avoids the mouse.
    if (form.requestSubmit) form.requestSubmit();
    else form.submit();
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
