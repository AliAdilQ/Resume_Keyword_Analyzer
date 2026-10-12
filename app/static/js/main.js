/* Progressive enhancement. Forms and navigation remain usable without JS. */
"use strict";

document.querySelectorAll("[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll("[data-loading]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (event.defaultPrevented || !form.checkValidity()) return;
    const button = form.querySelector(
      "button[type='submit'], button:not([type])",
    );
    if (button) {
      button.disabled = true;
      button.textContent = form.dataset.loading;
    }
    const notice = form.querySelector(".loading-notice");
    if (notice) notice.hidden = false;
  });
});

document.querySelectorAll("[data-password]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.password);
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    button.setAttribute("aria-label", show ? "Hide password" : "Show password");
    button.querySelector("i").className = `bi bi-eye${show ? "-slash" : ""}`;
  });
});

const fileInput = document.getElementById("resume");
const uploadZone = document.getElementById("upload-zone");
if (fileInput && uploadZone) {
  const showFile = () => {
    const file = fileInput.files[0];
    const selected = document.getElementById("upload-selected");
    fileInput.setCustomValidity("");
    selected.textContent = file
      ? `${file.name} · ${(file.size / 1024).toFixed(0)} KB`
      : "";
    if (file && file.size > 5 * 1024 * 1024) {
      fileInput.setCustomValidity("Choose a file smaller than 5 MB.");
      selected.textContent += " · File is too large";
    }
  };
  fileInput.addEventListener("change", showFile);
  uploadZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    uploadZone.classList.add("dragging");
  });
  uploadZone.addEventListener("dragleave", () =>
    uploadZone.classList.remove("dragging"),
  );
  uploadZone.addEventListener("drop", (event) => {
    event.preventDefault();
    uploadZone.classList.remove("dragging");
    if (event.dataTransfer.files.length) {
      const transfer = new DataTransfer();
      transfer.items.add(event.dataTransfer.files[0]);
      fileInput.files = transfer.files;
      showFile();
    }
  });
}

const jobDescription = document.getElementById("job_description");
if (jobDescription) {
  const updateCount = () => {
    document.getElementById("character-count").textContent =
      `${jobDescription.value.length.toLocaleString()} / 20,000`;
  };
  jobDescription.addEventListener("input", updateCount);
  updateCount();
  document
    .getElementById("load-sample")
    ?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const response = await fetch(
          "/static/samples/python_developer_job.txt",
        );
        if (!response.ok) throw new Error("Sample unavailable");
        jobDescription.value = await response.text();
        document.getElementById("job_title").value = "Python Developer";
        document.getElementById("company_name").value = "TechNova";
        updateCount();
      } catch (_) {
        window.alert("Could not load the sample job. Please try again.");
      } finally {
        button.disabled = false;
      }
    });
}

function readData(id) {
  const node = document.getElementById(id);
  return node ? JSON.parse(node.textContent) : null;
}

if (typeof Chart !== "undefined") {
  Chart.defaults.font.family = "Manrope, Segoe UI, sans-serif";
  Chart.defaults.font.size = 9;
  Chart.defaults.color = "#a0a8ba";
  Chart.defaults.borderColor = "#f1f2f7";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 7;
  Chart.defaults.plugins.legend.labels.padding = 20;
  Chart.defaults.animation.duration = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches
    ? 0
    : 450;
  const common = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: { maxRotation: 0 },
      },
      y: {
        beginAtZero: true,
        border: { display: false },
        ticks: { precision: 0, padding: 10 },
      },
    },
  };

  const trend = readData("trend-data");
  if (trend) {
    const canvas = document.getElementById("score-trend");
    const gradient = canvas.getContext("2d").createLinearGradient(0, 0, 0, 230);
    gradient.addColorStop(0, "#9a83e62b");
    gradient.addColorStop(1, "#9a83e602");
    new Chart(canvas, {
      type: "line",
      data: {
        labels: trend.labels,
        datasets: [
          {
            label: "Match score",
            data: trend.scores,
            borderColor: "#a18cde",
            backgroundColor: gradient,
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: "#fff",
            pointBorderWidth: 2,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        ...common,
        scales: {
          ...common.scales,
          x: {
            ...common.scales.x,
            ticks: {
              callback: function (value) {
                const label = this.getLabelForValue(value);
                return label.length > 15 ? label.slice(0, 13) + "…" : label;
              },
              maxRotation: 0,
            },
          },
          y: {
            ...common.scales.y,
            max: 100,
            ticks: { stepSize: 25, callback: (value) => `${value}%` },
          },
        },
      },
    });
  }
  const report = readData("result-data");
  if (report) {
    new Chart(document.getElementById("keyword-donut"), {
      type: "doughnut",
      data: {
        labels: ["Matched keywords", "Missing keywords"],
        datasets: [
          {
            data: [
              report.matched_keywords.length,
              report.missing_keywords.length,
            ],
            backgroundColor: ["#9a87df", "#efeaf9"],
            borderWidth: 0,
            hoverOffset: 5,
            borderRadius: 3,
            spacing: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "76%",
        plugins: { legend: { position: "bottom" } },
      },
    });
    new Chart(document.getElementById("keyword-frequency"), {
      type: "bar",
      data: {
        labels: report.top_frequency.labels,
        datasets: [
          {
            label: "Occurrences",
            data: report.top_frequency.values,
            backgroundColor: "#b6a7e8",
            hoverBackgroundColor: "#9a85de",
            borderRadius: 4,
            maxBarThickness: 16,
          },
        ],
      },
      options: {
        ...common,
        indexAxis: "y",
        scales: {
          x: { ...common.scales.y, ticks: { precision: 0 } },
          y: { grid: { display: false }, border: { display: false } },
        },
      },
    });
    new Chart(document.getElementById("keyword-comparison"), {
      type: "bar",
      data: {
        labels: report.comparison.labels,
        datasets: [
          {
            label: "Resume",
            data: report.comparison.resume,
            backgroundColor: "#a18cde",
            borderRadius: 4,
            maxBarThickness: 20,
          },
          {
            label: "Job description",
            data: report.comparison.job,
            backgroundColor: "#e4dcf6",
            borderRadius: 4,
            maxBarThickness: 20,
          },
        ],
      },
      options: {
        ...common,
        plugins: { legend: { position: "bottom" } },
        scales: {
          ...common.scales,
          x: { ...common.scales.x, ticks: { maxRotation: 40, minRotation: 0 } },
        },
      },
    });
  }
  const activity = readData("admin-data");
  if (activity) {
    new Chart(document.getElementById("admin-activity"), {
      type: "bar",
      data: {
        labels: activity.labels,
        datasets: [
          {
            label: "Analyses",
            data: activity.counts,
            backgroundColor: activity.counts.map((_, i) =>
              i === 6 ? "#9e86dc" : "#e7e0f5",
            ),
            borderRadius: 5,
            maxBarThickness: 30,
          },
        ],
      },
      options: common,
    });
  }
}

// Browsers can restore a disabled submit button from the back-forward cache.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) window.location.reload();
});
