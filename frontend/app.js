const state = {
  jobIds: JSON.parse(localStorage.getItem("jobIds") || "[]"),
  poll: null,
};

const downloadForm = document.querySelector("#downloadForm");
const jobsEl = document.querySelector("#jobs");
const messageEl = document.querySelector("#message");

function saveJobIds() {
  localStorage.setItem("jobIds", JSON.stringify(state.jobIds.slice(0, 25)));
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(body?.detail || "Request failed.");
  }
  return body;
}

function setMessage(text, isError = false) {
  messageEl.textContent = text;
  messageEl.style.color = isError ? "#b3261e" : "#646464";
}

function renderJobs(jobs) {
  if (!jobs.length) {
    jobsEl.innerHTML = `<p class="hint">No downloads yet.</p>`;
    return;
  }

  jobsEl.innerHTML = jobs
    .map((job) => {
      const archive =
        job.status === "complete"
          ? `<a class="archive" href="/api/downloads/${job.id}/archive" target="_blank" rel="noreferrer">Download zip</a>`
          : "";
      const detail = job.error || job.progress || "Queued.";
      return `
        <article class="job">
          <div>
            <div class="job-url">${job.url}</div>
            <p class="job-progress">${detail}</p>
            ${archive}
          </div>
          <span class="status ${job.status}">${job.status}</span>
        </article>
      `;
    })
    .join("");
}

async function loadJobs() {
  if (!state.jobIds.length) {
    renderJobs([]);
    return;
  }

  const results = await Promise.allSettled(
    state.jobIds.map((id) => api(`/api/downloads/${id}`)),
  );
  const jobs = results
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value);
  renderJobs(jobs);
}

function startPolling() {
  if (state.poll) return;
  state.poll = setInterval(loadJobs, 3000);
}

downloadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const submit = formEl.querySelector("button");

  submit.disabled = true;
  setMessage("Starting download...");
  try {
    const job = await api("/api/downloads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: form.get("url") }),
    });
    state.jobIds = [job.id, ...state.jobIds.filter((id) => id !== job.id)];
    saveJobIds();
    formEl.reset();
    setMessage("Download queued.");
    await loadJobs();
    startPolling();
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

loadJobs();
startPolling();
