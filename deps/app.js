// GOATS Dependencies Viewer — graph + matrix views with filtering/search.

let data = null;
let network = null;
let meta = {};                 // per-node derived info, keyed by node id
let nodeById = {};
let currentView = 'graph';     // 'graph' | 'matrix'
let currentFilter = 'all';     // 'all' | 'conflicts' | 'shared' | <sourceId>
let searchTerm = '';

const colors = {
    goats: '#58a6ff',
    tomtoolkit: '#3fb950',
    dragons: '#a371f7',
    jdaviz: '#d29922',
    conflict: '#f48771',
    ok: '#888'
};
const SOURCE_IDS = ['goats', 'tomtoolkit', 'dragons', 'jdaviz'];
const CONFLICT_STATUSES = ['conflict', 'invalid_range', 'conda_conflict'];

const isConflict = (n) => CONFLICT_STATUSES.includes(n.status);

// ---------------------------------------------------------------------------
// File loading
// ---------------------------------------------------------------------------

document.getElementById('network').addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
});

document.getElementById('network').addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
});

document.getElementById('jsonFile').addEventListener('change', (e) => {
    if (e.target.files[0]) loadFile(e.target.files[0]);
});

function applyData(json) {
    data = json;
    computeMeta();
    document.getElementById('uploadOverlay').classList.add('hidden');
    document.getElementById('toolbar').style.display = 'flex';
    updateStats();
    render();
}

function loadFile(file) {
    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            applyData(JSON.parse(event.target.result));
        } catch (err) {
            alert('Error parsing JSON: ' + err.message);
        }
    };
    reader.readAsText(file);
}

// Auto-load when opened as interactive.html?data=<url> (used by `check_deps.py --open`).
(function autoLoadFromQuery() {
    const src = new URLSearchParams(window.location.search).get('data');
    if (!src) return;
    fetch(src)
        .then(r => {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        })
        .then(applyData)
        .catch(err => console.error('Auto-load failed for "' + src + '":', err));
})();

// ---------------------------------------------------------------------------
// Derived data
// ---------------------------------------------------------------------------

function computeMeta() {
    meta = {};
    nodeById = {};
    data.nodes.forEach(n => {
        nodeById[n.id] = n;
        meta[n.id] = {
            inDegree: 0,
            requiringSources: new Set(),
            specBySource: {},        // sourceId -> [specs]
            neighbors: new Set()
        };
    });

    // Specs declared by each of the 4 sources (for the matrix cells).
    data.nodes.forEach(n => {
        (n.specs || []).forEach(s => {
            if (SOURCE_IDS.includes(s.from)) {
                (meta[n.id].specBySource[s.from] ||= []).push(s.spec || '*');
            }
        });
    });

    (data.edges || []).forEach(e => {
        if (meta[e.target]) {
            meta[e.target].inDegree++;
            if (SOURCE_IDS.includes(e.source)) meta[e.target].requiringSources.add(e.source);
        }
        if (meta[e.source]) meta[e.source].neighbors.add(e.target);
        if (meta[e.target]) meta[e.target].neighbors.add(e.source);
    });
}

function updateStats() {
    document.getElementById('totalPkgs').textContent = data.nodes.length;
    document.getElementById('okCount').textContent =
        data.nodes.filter(n => n.status === 'ok').length;
    document.getElementById('conflictCount').textContent =
        data.summary ? data.summary.conflicts : data.nodes.filter(isConflict).length;
    if (data.goats_version) {
        document.getElementById('goatsVersion').textContent = 'v' + data.goats_version;
    }
    const nConflicts = data.nodes.filter(isConflict).length;
    const nShared = data.nodes.filter(n => meta[n.id].requiringSources.size >= 2).length;
    document.getElementById('cntConflicts').textContent = '(' + nConflicts + ')';
    document.getElementById('cntShared').textContent = '(' + nShared + ')';
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

function baseFilterIds(filter) {
    const ids = new Set();
    if (filter === 'all') {
        data.nodes.forEach(n => ids.add(n.id));
    } else if (filter === 'conflicts') {
        // Conflict nodes plus their immediate neighbors, for context.
        data.nodes.filter(isConflict).forEach(n => {
            ids.add(n.id);
            meta[n.id].neighbors.forEach(x => ids.add(x));
        });
    } else if (filter === 'shared') {
        data.nodes.forEach(n => {
            if (meta[n.id].requiringSources.size >= 2) ids.add(n.id);
        });
        SOURCE_IDS.forEach(s => { if (nodeById[s]) ids.add(s); });
    } else if (SOURCE_IDS.includes(filter)) {
        // The source itself + everything it directly requires.
        ids.add(filter);
        (data.edges || []).forEach(e => {
            if (e.source === filter) ids.add(e.target);
        });
    }
    return ids;
}

function computeVisible() {
    let ids = baseFilterIds(currentFilter);
    if (searchTerm) {
        const q = searchTerm.toLowerCase();
        const matches = [...ids].filter(id => nodeById[id].label.toLowerCase().includes(q));
        const withCtx = new Set(matches);
        matches.forEach(id => meta[id].neighbors.forEach(n => { if (ids.has(n)) withCtx.add(n); }));
        ids = withCtx;
    }
    return ids;
}

// ---------------------------------------------------------------------------
// View switching
// ---------------------------------------------------------------------------

function render() {
    if (!data) return;
    if (currentView === 'matrix') buildMatrix();
    else loadGraph(currentView === 'sugiyama');
}

function setView(view) {
    if (!data || view === currentView) return;
    currentView = view;
    const isMatrix = view === 'matrix';
    document.getElementById('viewGraph').classList.toggle('active', view === 'graph');
    document.getElementById('viewSugiyama').classList.toggle('active', view === 'sugiyama');
    document.getElementById('viewMatrix').classList.toggle('active', isMatrix);
    document.getElementById('network').style.display = isMatrix ? 'none' : 'block';
    document.getElementById('matrix-container').style.display = isMatrix ? 'block' : 'none';
    document.querySelector('.legend').style.display = isMatrix ? 'none' : 'block';
    render();
}

function setFilter(filter) {
    if (!data) return;
    currentFilter = filter;
    document.querySelectorAll('#toolbar .btn[data-filter]').forEach(b => {
        b.classList.toggle('active', b.dataset.filter === filter);
    });
    render();
}

function onSearch(value) {
    searchTerm = value.trim();
    render();
}

// ---------------------------------------------------------------------------
// Graph view
// ---------------------------------------------------------------------------

function nodeColor(pkg) {
    if (isConflict(pkg)) return colors.conflict;
    if (SOURCE_IDS.includes(pkg.id)) return colors[pkg.id];
    return colors.ok;
}

function nodeSize(pkg) {
    if (SOURCE_IDS.includes(pkg.id)) return 42;
    // Scale by how many packages depend on it (numpy huge, leaves small).
    return 14 + Math.min(meta[pkg.id].inDegree * 1.6, 30);
}

function loadGraph(hierarchical = false) {
    const visible = computeVisible();
    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();

    data.nodes.forEach(pkg => {
        if (!visible.has(pkg.id)) return;
        const color = nodeColor(pkg);
        nodes.add({
            id: pkg.id,
            label: pkg.label,
            color: {
                background: color,
                border: color,
                highlight: { background: color, border: '#fff' }
            },
            font: { size: 12, color: '#fff', face: 'Arial' },
            borderWidth: 2,
            borderWidthSelected: 3,
            size: nodeSize(pkg),
            title: `${pkg.label}\nStatus: ${pkg.status}\nRequired by: ${meta[pkg.id].inDegree}`
        });
    });

    (data.edges || []).forEach(edge => {
        if (!visible.has(edge.source) || !visible.has(edge.target)) return;
        const conflict = edge.conflict;
        edges.add({
            from: edge.source,
            to: edge.target,
            label: edge.label || '',
            color: conflict ? { color: '#f48771', highlight: '#ff6b6b' } : '#555',
            dashes: conflict,
            width: conflict ? 2 : 1,
            font: {
                size: 12,
                face: "'Monaco', 'Courier New', monospace",
                color: conflict ? '#ffb3a3' : '#cdd9e5',
                background: conflict ? '#3a1d18' : '#161b22',
                strokeWidth: 0,
                align: 'middle',
                vadjust: -2
            }
        });
    });

    const container = document.getElementById('network');
    const options = {
        interaction: {
            navigationButtons: false,
            keyboard: true,
            zoomView: true,
            dragView: true,
            hideEdgesOnDrag: false
        },
        nodes: {
            shape: 'dot',
            scaling: { label: { enabled: true, min: 14, max: 30 } }
        }
    };

    if (hierarchical) {
        // Sugiyama-style layered layout: sources on top, deps flowing down.
        options.layout = {
            hierarchical: {
                enabled: true,
                direction: 'UD',
                sortMethod: 'directed',
                shakeTowards: 'roots',
                levelSeparation: 160,
                nodeSpacing: 110,
                treeSpacing: 220
            }
        };
        options.physics = { enabled: false };
        options.edges = {
            smooth: { type: 'cubicBezier', forceDirection: 'vertical', roundness: 0.55 }
        };
    } else {
        options.physics = {
            enabled: true,
            barnesHut: {
                gravitationalConstant: -50000,
                centralGravity: 0.5,
                springLength: 250,
                springConstant: 0.04
            },
            solver: 'barnesHut',
            timestep: 0.35,
            stabilization: { iterations: 200 }
        };
    }

    if (network) network.destroy();
    network = new vis.Network(container, { nodes, edges }, options);
    network.on('click', (params) => {
        if (params.nodes.length > 0) showPanel(params.nodes[0]);
    });
}

// ---------------------------------------------------------------------------
// Matrix view
// ---------------------------------------------------------------------------

function buildMatrix() {
    const visible = computeVisible();
    const rows = data.nodes.filter(n =>
        !SOURCE_IDS.includes(n.id) &&
        visible.has(n.id) &&
        SOURCE_IDS.some(s => meta[n.id].specBySource[s])
    );

    rows.sort((a, b) => {
        const ca = isConflict(a) ? 1 : 0;
        const cb = isConflict(b) ? 1 : 0;
        if (ca !== cb) return cb - ca;
        return meta[b.id].inDegree - meta[a.id].inDegree;
    });

    const container = document.getElementById('matrix-container');
    if (rows.length === 0) {
        container.innerHTML = '<div class="matrix-empty">No packages match the current filter.</div>';
        return;
    }

    const labels = { goats: 'GOATS', tomtoolkit: 'TOMToolkit', dragons: 'DRAGONS', jdaviz: 'JDAViz' };
    let html = '<table class="matrix-table"><thead><tr>' +
        '<th>Package</th><th>Req&nbsp;by</th>' +
        SOURCE_IDS.map(s => `<th class="src-${s}">${labels[s]}</th>`).join('') +
        '</tr></thead><tbody>';

    rows.forEach(n => {
        const m = meta[n.id];
        const conflict = isConflict(n);
        let pkgCell = n.label;
        if (conflict) pkgCell += '<span class="badge-mini conflict">' + n.status.replace('_', ' ') + '</span>';
        else if (m.requiringSources.size >= 2) pkgCell += '<span class="badge-mini shared">shared</span>';

        const cells = SOURCE_IDS.map(s => {
            const specs = m.specBySource[s];
            return specs
                ? `<td class="spec has">${specs.join(', ')}</td>`
                : '<td class="spec">·</td>';
        }).join('');

        html += `<tr class="${conflict ? 'conflict' : ''}" onclick="showPanel('${n.id}')">` +
            `<td class="pkg">${pkgCell}</td><td>${m.inDegree}</td>${cells}</tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function showPanel(pkgId) {
    const pkg = nodeById[pkgId];
    if (!pkg) return;

    document.getElementById('panelEmpty').style.display = 'none';
    document.getElementById('panelTitle').textContent = pkg.label;

    let statusClass, statusText;
    if (pkg.status === 'source') {
        statusClass = 'source';
        statusText = '📦 SOURCE';
    } else if (pkg.status === 'ok') {
        statusClass = 'ok';
        statusText = '✅ OK';
    } else {
        statusClass = 'conflict';
        statusText = '⚠️ ' + pkg.status.replace('_', ' ').toUpperCase();
    }
    document.getElementById('panelStatus').innerHTML =
        `<span class="status-badge ${statusClass}">${statusText}</span>`;

    const panelContent = document.getElementById('panelContent');
    panelContent.style.display = 'block';

    let html = '';

    if (pkg.issue) {
        html += `<div class="issue-box">⚠️ ${pkg.issue}</div>`;
    }

    if (pkg.specs && pkg.specs.length > 0) {
        html += `<div class="section">
            <div class="section-title">📋 Version Specs (${pkg.specs.length})</div>
            <div class="scroll-container">`;
        pkg.specs.forEach(s => {
            const hasConflict = s.spec.includes('!');
            const srcClass = SOURCE_IDS.includes(s.from) ? 'src-' + s.from : '';
            const value = s.spec
                ? `<code class="spec-value">${s.spec}</code>`
                : `<code class="spec-value any">any</code>`;
            html += `
                <div class="spec-item ${hasConflict ? 'conflict' : ''}">
                    <span class="spec-source ${srcClass}">${s.from}</span>
                    ${value}
                </div>
            `;
        });
        html += `</div></div>`;
    }

    if (pkg.lower_bound || pkg.upper_bound) {
        const bounds = [];
        if (pkg.lower_bound) bounds.push(pkg.lower_bound);
        if (pkg.upper_bound) bounds.push(pkg.upper_bound);
        html += `<div class="section">
            <div class="section-title">🎯 Version Bounds</div>
            <div class="bounds-box">${bounds.join(' AND ')}</div>
        </div>`;
    }

    if (data.edges) {
        const requiredBy = data.edges.filter(e => e.target === pkgId);
        if (requiredBy.length > 0) {
            const sources = [...new Set(requiredBy.map(e => e.source))];
            html += `<div class="section">
                <div class="section-title">📌 Required by (${sources.length})</div>
                <div class="requires-list">`;
            sources.forEach(source => {
                const tagClass = SOURCE_IDS.includes(source) ? source : '';
                html += `<span class="tag ${tagClass}">${source}</span>`;
            });
            html += `</div></div>`;
        }

        const deps = data.edges.filter(e => e.source === pkgId);
        if (deps.length > 0) {
            html += `<div class="section">
                <div class="section-title">📦 Dependencies (${deps.length})</div>
                <div class="requires-list">`;
            deps.slice(0, 20).forEach(dep => {
                html += `<span class="tag">${dep.target}</span>`;
            });
            if (deps.length > 20) {
                html += `<span class="tag" style="opacity: 0.6;">+${deps.length - 20} more</span>`;
            }
            html += `</div></div>`;
        }
    }

    panelContent.innerHTML = html;
}
