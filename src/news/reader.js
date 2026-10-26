/* A story is read only after an explicit action; publisher links never change it. */
(() => {
  "use strict";
  // Retain the existing browser key so returning readers keep their read state.
  const storageKey = "daily-news-library-read-v1";
  const cards = [...document.querySelectorAll(".reader-story")];
  const topic = document.getElementById("topic-filter");
  const geography = document.getElementById("geography-filter");
  const unread = document.getElementById("unread-filter");
  const featured = document.getElementById("featured-section");
  const collection = document.getElementById("collection-cards");
  const week = document.getElementById("week-overview");
  const originalFeatured = [...featured.querySelectorAll(".reader-story")];
  const status = document.getElementById("storage-status");
  let read = new Set();
  let storageAvailable = true;
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (Array.isArray(saved)) read = new Set(saved.filter(key => typeof key === "string"));
  } catch (_) {
    storageAvailable = false;
  }
  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify([...read])); }
    catch (_) { storageAvailable = false; }
  }
  function update() {
    const filtering = Boolean(topic.value || geography.value || unread.checked);
    if (filtering) {
      [...originalFeatured].reverse().forEach(card => collection.insertBefore(card, collection.firstChild));
    } else {
      originalFeatured.forEach(card => featured.appendChild(card));
    }
    featured.hidden = filtering;
    let visible = 0;
    let matchingHistory = 0;
    for (const card of cards) {
      const isRead = read.has(card.dataset.readKey);
      const matches = (!topic.value || JSON.parse(card.dataset.topics).includes(topic.value)) &&
        (!geography.value || JSON.parse(card.dataset.geography).includes(geography.value)) &&
        (!unread.checked || !isRead);
      card.hidden = !matches;
      card.classList.toggle("is-read", isRead);
      card.querySelector(".read-toggle").textContent = isRead ? "Mark unread" : "Mark read";
      card.querySelector(".read-toggle").setAttribute("aria-pressed", String(isRead));
      card.querySelector(".read-label").textContent = isRead ? "Read" : "Unread";
      if (matches && week.contains(card)) matchingHistory += 1;
      if (matches && (!week.contains(card) || week.open)) visible += 1;
    }
    const hiddenHistoryMatches = !week.open && matchingHistory > 0;
    document.getElementById("no-results").hidden = visible > 0;
    document.getElementById("no-results-message").textContent = hiddenHistoryMatches
      ? "No matches in this edition. Earlier reports match in the seven-day overview."
      : "No stories match these filters.";
    document.getElementById("show-history").hidden = !hiddenHistoryMatches;
    const count = document.getElementById("result-count");
    count.hidden = false;
    count.textContent = `${visible} ${visible === 1 ? "report" : "reports"} shown${week.open ? " across recent editions" : " in this edition"}.`;
    if (!storageAvailable) status.textContent = "Browser storage is unavailable. Read state lasts for this page only; reading and filters still work.";
  }
  cards.forEach(card => {
    const button = card.querySelector(".read-toggle");
    button.hidden = false;
    button.addEventListener("click", () => {
      const key = card.dataset.readKey;
      if (read.has(key)) read.delete(key); else read.add(key);
      persist();
      update();
      if (card.hidden && document.activeElement === button) {
        const next = cards.slice(cards.indexOf(card) + 1).find(item => !item.hidden && (!week.contains(item) || week.open))
          || cards.find(item => !item.hidden && (!week.contains(item) || week.open));
        (next ? next.querySelector(".read-toggle") : unread).focus();
      }
    });
  });
  document.querySelector(".reader-controls").hidden = false;
  [topic, geography, unread].forEach(control => control.addEventListener("change", update));
  week.addEventListener("toggle", update);
  document.getElementById("show-history").addEventListener("click", () => {
    week.open = true;
    update();
    week.querySelector("summary").focus();
  });
  document.getElementById("reset-read").addEventListener("click", () => {
    read.clear();
    persist();
    update();
  });
  window.addEventListener("storage", event => {
    if (event.key !== storageKey) return;
    try {
      const saved = JSON.parse(event.newValue || "[]");
      if (Array.isArray(saved)) read = new Set(saved.filter(key => typeof key === "string"));
      update();
    } catch (_) { /* Keep this page's explicit read state when another tab stores invalid data. */ }
  });
  update();
})();
