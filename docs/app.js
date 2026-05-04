"use strict";

const AUTO_REFRESH_MS = 600_000;   // 10 minutes — same cadence as the cron
const STATUS_URL = "./data/status.json";

const $ = (sel) => document.querySelector(sel);
const sinceSel = $("#since");
const sourceSel = $("#source");
const refreshBtn = $("#refresh");
const statusEl = $("#status");
const feedEl = $("#feed");
const watchedEl = $("#watched");
const tpl = $("#row-tpl");

let timer = null;
let cache = { rows: [], generated_at: null, watched_repos: [] };

function timeAgo(iso) {
    if (!iso) return "—";
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return iso;
    const diff = Math.max(0, Date.now() - t);
    const m = Math.floor(diff / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
}

function parseSinceMs(value) {
    if (!value) return 24 * 3600 * 1000;
    const num = parseInt(value, 10);
    if (value.endsWith("h")) return num * 3600 * 1000;
    if (value.endsWith("d")) return num * 86400 * 1000;
    return num;
}

function applyFilters(rows) {
    const sinceMs = parseSinceMs(sinceSel.value);
    const cutoff = Date.now() - sinceMs;
    const sourceFilter = sourceSel.value;
    return rows.filter((r) => {
        if (sourceFilter !== "all" && r.source_tag !== sourceFilter) return false;
        const ts = Date.parse(r.when);
        if (Number.isFinite(ts) && ts < cutoff) return false;
        return true;
    });
}

function renderRow(row) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".when").textContent = timeAgo(row.when);

    const tag = node.querySelector(".tag");
    tag.textContent = row.source_tag || "human";
    tag.classList.add(`tag-${row.source_tag || "human"}`);

    const repo = node.querySelector(".repo");
    repo.textContent = row.repo;
    if (row.links && row.links.pr) {
        repo.href = row.links.pr;
    } else if (row.links && row.links.commit) {
        repo.href = row.links.commit;
    } else {
        repo.href = `https://github.com/${row.repo}`;
    }

    node.querySelector(".branch").textContent = row.branch || "";
    node.querySelector(".kind").textContent = (row.kind || "").replace(/_/g, " ");
    node.querySelector(".title").textContent = row.title || "";
    node.querySelector(".actor").textContent = row.actor || "";

    const ci = node.querySelector(".ci");
    if (row.ci && (row.ci.url || row.ci.conclusion || row.ci.status)) {
        ci.textContent = row.ci.conclusion || row.ci.status || "ci";
        ci.href = row.ci.url || "#";
        ci.classList.add(`ci-${row.ci.color || "grey"}`);
    } else {
        ci.classList.add("ci-empty");
        ci.textContent = "—";
    }
    return node;
}

function render() {
    const rows = applyFilters(cache.rows || []);
    feedEl.replaceChildren(...rows.map(renderRow));
    const watched = cache.watched_repos || [];
    watchedEl.textContent =
        `watching ${watched.length} repos · ` +
        `data generated ${timeAgo(cache.generated_at)} · ` +
        (watched.join(" · ") || "(none yet — first cron run pending)");
    statusEl.textContent =
        `${rows.length}/${(cache.rows || []).length} rows · ` +
        `auto-refresh ${Math.round(AUTO_REFRESH_MS / 60000)}m`;
}

async function load() {
    statusEl.textContent = "loading…";
    try {
        const resp = await fetch(`${STATUS_URL}?t=${Date.now()}`, { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        cache = await resp.json();
        render();
    } catch (err) {
        statusEl.textContent = `error: ${err.message}`;
    }
}

function schedule() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
        if (document.visibilityState === "visible") load();
    }, AUTO_REFRESH_MS);
}

sinceSel.addEventListener("change", render);
sourceSel.addEventListener("change", render);
refreshBtn.addEventListener("click", load);
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") load();
});

load();
schedule();
