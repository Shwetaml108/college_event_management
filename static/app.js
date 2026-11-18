const grid = document.querySelector("#events-grid");
const searchInput = document.querySelector("#event-search");
const eventTotal = document.querySelector("#event-total");
const loadError = document.querySelector("#load-error");
const dialog = document.querySelector("#event-dialog");
const form = document.querySelector("#event-form");
const formError = document.querySelector("#form-error");
const attendeeId = getAttendeeId();

let events = [];
let selectedCategory = "All";

function getAttendeeId() {
  const stored = localStorage.getItem("campus-events-attendee");
  if (stored) return stored;
  const id = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `student-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem("campus-events-attendee", id);
  return id;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatDate(value) {
  const date = new Date(value);
  return {
    month: new Intl.DateTimeFormat("en", { month: "short" }).format(date).toUpperCase(),
    day: new Intl.DateTimeFormat("en", { day: "2-digit" }).format(date),
    detail: new Intl.DateTimeFormat("en", {
      weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    }).format(date),
  };
}

function renderEvents() {
  const query = searchInput.value.trim().toLowerCase();
  const visibleEvents = events.filter((event) => {
    const matchesCategory = selectedCategory === "All" || event.category === selectedCategory;
    const searchable = `${event.title} ${event.description} ${event.location} ${event.organizer}`.toLowerCase();
    return matchesCategory && searchable.includes(query);
  });

  eventTotal.textContent = `${visibleEvents.length} ${visibleEvents.length === 1 ? "EVENT" : "EVENTS"} TO GET INTO`;
  if (visibleEvents.length === 0) {
    grid.innerHTML = `<div class="empty-state"><span class="empty-mark">✳</span><h3>No plans found. Yet.</h3><p>Try another search or start something of your own.</p><button class="button button-dark" data-action="create" type="button">Create an event <span aria-hidden="true">↗</span></button></div>`;
    return;
  }

  grid.innerHTML = visibleEvents.map((event, index) => {
    const date = formatDate(event.start_at);
    const full = event.rsvp_count >= event.capacity && !event.attending;
    const spots = Math.max(0, event.capacity - event.rsvp_count);
    return `
      <article class="event-card" style="--card-index:${index}">
        <div class="event-cover cover-${escapeHtml(event.category.toLowerCase())}">
          <span class="category-pill">${escapeHtml(event.category)}</span>
          <div class="cover-ornament" aria-hidden="true">${coverMark(event.category)}</div>
          <div class="date-stamp"><span>${date.month}</span><strong>${date.day}</strong></div>
          <span class="cover-index">NO. ${String(index + 1).padStart(2, "0")}</span>
        </div>
        <div class="event-content">
          <div class="event-date">${escapeHtml(date.detail)}</div>
          <h3>${escapeHtml(event.title)}</h3>
          <p class="event-description">${escapeHtml(event.description)}</p>
          <div class="event-meta">
            <span><span aria-hidden="true">⌖</span> ${escapeHtml(event.location)}</span>
            <span><span aria-hidden="true">◉</span> ${escapeHtml(event.organizer)}</span>
          </div>
          <div class="event-actions">
            <div class="attendance"><strong>${event.rsvp_count}</strong><span> / ${event.capacity} going</span></div>
            <button class="rsvp-button ${event.attending ? "is-going" : ""}" data-action="rsvp" data-id="${escapeHtml(event.id)}" data-attending="${!event.attending}" ${full ? "disabled" : ""} type="button">
              ${event.attending ? "You're going ✓" : full ? "Full" : "Count me in ↗"}
            </button>
          </div>
          <div class="host-tools">
            <button type="button" data-action="edit" data-id="${escapeHtml(event.id)}">Edit</button>
            <button type="button" data-action="delete" data-id="${escapeHtml(event.id)}">Remove</button>
            <span>${spots === 0 ? "All spots filled" : `${spots} ${spots === 1 ? "spot" : "spots"} left`}</span>
          </div>
        </div>
      </article>`;
  }).join("");
}

function coverMark(category) {
  const marks = { Academic: "✳", Arts: "✺", Career: "↗", Community: "✿", Sports: "✹", Tech: "⌘" };
  return marks[category] || "✳";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Something went wrong. Please try again.");
  return result;
}

async function loadEvents() {
  loadError.hidden = true;
  try {
    const result = await request(`/api/events?attendee_id=${encodeURIComponent(attendeeId)}`);
    events = result.events;
    renderEvents();
  } catch (error) {
    loadError.textContent = error.message;
    loadError.hidden = false;
  }
}

function openDialog(event = null) {
  form.reset();
  formError.hidden = true;
  form.dataset.eventId = event?.id || "";
  document.querySelector("#dialog-title").textContent = event ? "Edit event" : "Create an event";
  document.querySelector(".submit-event").innerHTML = event
    ? 'Save changes <span aria-hidden="true">↗</span>'
    : 'Add to the calendar <span aria-hidden="true">↗</span>';
  if (event) {
    for (const [key, value] of Object.entries(event)) {
      const input = form.elements.namedItem(key);
      if (input) input.value = key === "start_at" ? value.slice(0, 16) : value;
    }
  }
  dialog.showModal();
}

document.querySelector("#create-event-button").addEventListener("click", () => openDialog());
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
searchInput.addEventListener("input", renderEvents);

document.querySelector("#category-filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  selectedCategory = button.dataset.category;
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.classList.toggle("selected", chip === button);
    chip.setAttribute("aria-pressed", String(chip === button));
  });
  renderEvents();
});

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    searchInput.focus();
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;
  if (action === "create") {
    openDialog();
    return;
  }
  try {
    if (action === "rsvp") {
      await request(`/api/events/${encodeURIComponent(id)}/rsvp`, {
        method: "POST",
        body: JSON.stringify({ attendee_id: attendeeId, attending: button.dataset.attending === "true" }),
      });
    } else if (action === "edit") {
      openDialog(events.find((item) => item.id === id));
      return;
    } else if (action === "delete") {
      if (!window.confirm("Remove this event from the calendar?")) return;
      await request(`/api/events/${encodeURIComponent(id)}`, { method: "DELETE" });
    }
    await loadEvents();
  } catch (error) {
    window.alert(error.message);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  data.capacity = Number(data.capacity);
  const eventId = form.dataset.eventId;
  try {
    await request(eventId ? `/api/events/${encodeURIComponent(eventId)}` : "/api/events", {
      method: eventId ? "PUT" : "POST",
      body: JSON.stringify(data),
    });
    dialog.close();
    await loadEvents();
  } catch (error) {
    formError.textContent = error.message;
    formError.hidden = false;
  }
});

loadEvents();
