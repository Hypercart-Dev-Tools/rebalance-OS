"use strict";

const $ = (sel) => document.querySelector(sel);
const sinceSel = $("#since");
const refreshBtn = $("#refresh");
const statusEl = $("#status");
const feedEl = $("#feed");
const watchedEl = $("#watched");
const tpl = $("#row-tpl");

let timer = null;

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

function renderRow(row) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".when").textContent = timeAgo(row.when);
    const tag = node.querySelector(".tag");
    tag.textContent = row.source_tag;
    tag.classList.add(`tag-${row.source_tag}`);
    const repo = node.querySelector(".repo");
    repo.textContent = row.repo;
    repo.href = `https://github.com/${row.repo}`;
    node.querySelector(".branch").textContent = row.branch || "";
    node.querySelector(".kind").textContent = row.kind.replace(/_/g, " ");
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
    if (row.links && row.links.pr) {
        repo.href = row.links.pr;
    } else if (row.links && row.links.commit) {
        repo.href = row.links.commit;
    }
    return node;
}

async function load() {
    const since = sinceSel.value;
    statusEl.textContent = "loading…";
    try {
        const resp = await fetch(`/api/activity?since=${encodeURIComponent(since)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        feedEl.replaceChildren(...data.rows.map(renderRow));
        const ingest = data.ingest || {};
        const watched = (ingest.watched_repos || []).join(" · ") || "(no repos yet — try refresh)";
        watchedEl.textContent = `watching ${ (ingest.watched_repos || []).length } repos · last sync ${timeAgo(ingest.last_finished_at)} · ${watched}`;
        statusEl.textContent = `${data.count} rows · auto-refresh ${Math.round(window.AUTO_REFRESH_MS / 60000)}m`;
    } catch (err) {
        statusEl.textContent = `error: ${err.message}`;
    }
}

async function manualRefresh() {
    refreshBtn.disabled = true;
    statusEl.textContent = "refreshing GitHub…";
    try {
        const resp = await fetch("/api/refresh", { method: "POST" });
        if (resp.status === 409) {
            statusEl.textContent = "refresh already running…";
        } else if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
    } catch (err) {
        statusEl.textContent = `refresh failed: ${err.message}`;
    } finally {
        refreshBtn.disabled = false;
        await load();
    }
}

function schedule() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
        if (document.visibilityState === "visible") load();
    }, window.AUTO_REFRESH_MS || 600000);
}

sinceSel.addEventListener("change", load);
refreshBtn.addEventListener("click", manualRefresh);
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") load();
});

load();
schedule();
