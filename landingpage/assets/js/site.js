/* ════════════════════════════════════════════════════════════════════════════
   KIWERK OS · gemeinsames Skript aller Seiten

   Progressive Enhancement: Ohne dieses Skript ist die Seite vollständig
   benutzbar. Es liefert nur (1) das ausklappbare Menü auf kleinen Schirmen und
   (2) den Auftritt des Hero. Alle Blöcke prüfen zuerst, ob es ihr Element auf
   dieser Seite überhaupt gibt.

   Kein Tracking, keine externen Aufrufe, kein Cookie, kein Storage.
   ════════════════════════════════════════════════════════════════════════════ */
(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.add('js');
  if (!reduce) document.documentElement.classList.add('motion');

  /* ══════════════════════════════════════════════  Mobile Navigation  ══
     Das Panel ist im CSS erst durch .js versteckt, fällt das Skript aus,
     bleibt die Navigation als umbrechende Zeile sichtbar. */
  const toggle = document.querySelector('.navtoggle');
  const panel = document.getElementById('nav');
  if (toggle && panel) {
    const setOpen = open => {
      panel.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
    };
    toggle.addEventListener('click', () => {
      setOpen(!panel.classList.contains('is-open'));
    });
    // Auf einer Mehrseiten-Website führt jeder Klick fort, das Panel muss
    // trotzdem schließen, falls der Link auf dieselbe Seite zeigt.
    panel.addEventListener('click', e => {
      if (e.target.closest('a')) setOpen(false);
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && panel.classList.contains('is-open')) {
        setOpen(false);
        toggle.focus();
      }
    });
    document.addEventListener('click', e => {
      if (!panel.classList.contains('is-open')) return;
      if (!e.target.closest('.masthead')) setOpen(false);
    });
    // Beim Wechsel auf die Desktopbreite darf kein halboffener Zustand bleiben
    window.matchMedia('(min-width: 1081px)').addEventListener('change', e => {
      if (e.matches) setOpen(false);
    });
  }

  /* ══════════════════════════════════════════════════  Auftritt Hero  ══
     Nicht allein an rAF hängen: in einem Hintergrund-Tab feuert das nicht und
     der Hero stünde dauerhaft auf opacity 0. */
  const hero = document.getElementById('hero');
  if (hero) {
    const enter = () => hero.classList.add('is-in');
    requestAnimationFrame(enter);
    setTimeout(enter, 120);
  }

  /* ══════════════════════════════════════════════  Motto-Nachhall  ══
     Die orange Sprechblase dreht genau einmal ein, wenn der Satz in den Blick
     kommt, der einzige Nachhall der Hero-Geste. */
  const motto = document.getElementById('motto');
  if (motto) {
    if (window.IntersectionObserver && !reduce) {
      const io = new IntersectionObserver(([e]) => {
        if (e.isIntersecting) { motto.classList.add('is-in'); io.disconnect(); }
      }, {threshold: .35});
      io.observe(motto);
    } else {
      motto.classList.add('is-in');
    }
  }
})();
