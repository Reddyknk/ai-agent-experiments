document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelectorAll('.tab');
  const pages = document.querySelectorAll('.page');

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((item) => item.classList.toggle('active', item === tab));
      pages.forEach((page) => page.classList.toggle('active', page.id === `page-${tab.dataset.page}`));
    });
  });

  const chatForm = document.getElementById('chat-form');
  const chatBox = document.getElementById('chat-box');
  const evidenceList = document.getElementById('evidence-list');
  const shutdownModal = document.getElementById('shutdown-modal');
  const shutdownInput = document.getElementById('shutdown-confirm-input');
  const confirmShutdownBtn = document.getElementById('confirm-shutdown-btn');

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
    }[character]));
  }

  function createMessage(text, sender, logs = []) {
    const wrapper = document.createElement('div');
    wrapper.className = `message ${sender}`;
    const label = sender === 'user' ? 'You' : 'Agent';
    wrapper.innerHTML = `<span class="meta">${label}</span><div>${escapeHtml(text).replaceAll('\n', '<br>')}</div>`;
    if (sender === 'agent' && logs.length) {
      const details = document.createElement('div');
      details.className = 'response-details';
      details.innerHTML = `<button type="button" class="show-logs-btn">Show Logs</button><div class="response-logs collapsed">${logs.map((log) => `<div class="log-bubble"><strong>${escapeHtml(log.component)}</strong><span>${escapeHtml(log.label)} · ${escapeHtml(log.elapsed_ms)} ms</span><pre>${escapeHtml(JSON.stringify(log, null, 2))}</pre></div>`).join('')}</div>`;
      details.querySelector('.show-logs-btn').addEventListener('click', () => {
        const logPanel = details.querySelector('.response-logs');
        logPanel.classList.toggle('collapsed');
        details.querySelector('.show-logs-btn').textContent = logPanel.classList.contains('collapsed') ? 'Show Logs' : 'Hide Logs';
      });
      wrapper.appendChild(details);
    }
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    createMessage(message, 'user');
    input.value = '';

    const payload = {
      message,
      agent: document.getElementById('agent-select').value,
      max_turns: Number(document.getElementById('max-turns').value || 3),
      skill_selector: document.getElementById('skill-selector').value,
      model: document.getElementById('model-select').value,
      temperature: Number(document.getElementById('temperature').value || 0.7),
      max_tokens: Number(document.getElementById('max-tokens').value || 256),
      doc_threshold: Number(document.getElementById('doc-threshold').value || 0.3),
      rag_chunks: Number(document.getElementById('rag-chunks').value || 5),
      skill_threshold: Number(document.getElementById('threshold').value || 0.2),
      custom_endpoint: document.getElementById('custom-endpoint').value,
    };

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    const answer = data.response || 'No response returned.';
    createMessage(answer, 'agent', data.logs || []);

    renderEvidence(data.evidence || []);
  });

  document.getElementById('model-select').addEventListener('change', (event) => {
    document.getElementById('custom-endpoint-field').classList.toggle('visible-control', event.target.value === 'Custom model');
  });

  document.getElementById('skill-selector').addEventListener('change', (event) => {
    document.getElementById('skill-threshold-field').classList.toggle('visible-control', event.target.value === 'vector_store');
  });

  function renderEvidence(evidence) {
    if (!evidence.length) {
      evidenceList.innerHTML = '<p class="empty-state">No matching context found.</p>';
      return;
    }
    const groups = evidence.reduce((result, item) => {
      const key = item.group || item.title || 'Retrieved context';
      if (!result[key]) result[key] = [];
      result[key].push(item);
      return result;
    }, {});
    evidenceList.innerHTML = Object.entries(groups).map(([group, items]) => `
      <section class="evidence-group">
        <h4>${group}</h4>
        ${items.map((item) => `
          <article class="evidence-item">
            <div class="evidence-item-heading">
              <strong>${item.title || 'Evidence'}</strong>
              <span>${item.source || ''}</span>
            </div>
            <p>${item.content || item.text || ''}</p>
            ${item.score !== undefined ? `<small>Distance: ${Number(item.score).toFixed(3)}</small>` : ''}
          </article>
        `).join('')}
      </section>
    `).join('');
  }

  document.getElementById('shutdown-button').addEventListener('click', () => {
    shutdownModal.classList.remove('hidden');
  });

  document.getElementById('refresh-audit-btn').addEventListener('click', refreshDashboard);

  document.getElementById('clear-logs-btn').addEventListener('click', () => {
    document.getElementById('clear-logs-modal').classList.remove('hidden');
  });

  document.getElementById('cancel-clear-logs-btn').addEventListener('click', () => {
    document.getElementById('clear-logs-modal').classList.add('hidden');
  });

  document.getElementById('confirm-clear-logs-btn').addEventListener('click', async () => {
    const response = await fetch('/api/logs/clear', { method: 'POST' });
    if (response.ok) {
      document.getElementById('clear-logs-modal').classList.add('hidden');
      renderEvents([], '');
      await refreshDashboard();
    }
  });

  document.getElementById('cancel-shutdown-btn').addEventListener('click', () => {
    shutdownModal.classList.add('hidden');
    shutdownInput.value = '';
    confirmShutdownBtn.disabled = true;
  });

  shutdownInput.addEventListener('input', () => {
    confirmShutdownBtn.disabled = shutdownInput.value.trim() !== 'Shutdown the service';
  });

  confirmShutdownBtn.addEventListener('click', async () => {
    const res = await fetch('/api/shutdown', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: shutdownInput.value.trim() }),
    });

    if (res.ok) {
      shutdownModal.classList.add('hidden');
      alert('Shutdown request acknowledged.');
    }
  });

  document.getElementById('update-skills-btn').addEventListener('click', async () => {
    await fetch('/api/skills/update', { method: 'POST' });
    alert('Skill database update requested.');
  });

  document.getElementById('populate-db-btn').addEventListener('click', async () => {
    const source = document.getElementById('vector-source').value || 'sample_docs';
    const res = await fetch('/api/vector/populate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source,
        chunk_size: Number(document.getElementById('chunk-size').value || 1200),
        chunk_overlap: Number(document.getElementById('chunk-overlap').value || 150),
      }),
    });
    const data = await res.json();
    alert(data.success ? 'Vector database populated.' : 'Failed to populate vector database.');
    refreshStats();
    refreshDocuments();
  });

  document.getElementById('reset-db-btn').addEventListener('click', async () => {
    await fetch('/api/vector/reset', { method: 'POST' });
    alert('Database reset requested.');
    refreshStats();
    refreshDocuments();
  });

  const embedderSelect = document.getElementById('embedder-select');
  const embeddingModal = document.getElementById('embedding-model-modal');
  const embeddingInput = document.getElementById('embedding-confirm-input');
  const confirmEmbeddingBtn = document.getElementById('confirm-embedding-btn');
  let pendingEmbeddingModel = '';
  embedderSelect.addEventListener('change', () => {
    pendingEmbeddingModel = embedderSelect.value;
    embeddingModal.classList.remove('hidden');
  });
  embeddingInput.addEventListener('input', () => {
    confirmEmbeddingBtn.disabled = embeddingInput.value.trim() !== 'Change the embedding model';
  });
  document.getElementById('cancel-embedding-btn').addEventListener('click', () => {
    embeddingModal.classList.add('hidden');
    embeddingInput.value = '';
    confirmEmbeddingBtn.disabled = true;
  });
  confirmEmbeddingBtn.addEventListener('click', async () => {
    const response = await fetch('/api/embedding-models/change', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: pendingEmbeddingModel, confirm: embeddingInput.value.trim() }),
    });
    const data = await response.json();
    alert(data.message || data.error || 'Embedding model update complete.');
    embeddingModal.classList.add('hidden');
    refreshStats();
    refreshDocuments();
  });

  document.querySelectorAll('.sample-link').forEach((button) => {
    button.addEventListener('click', () => {
      document.getElementById('vector-source').value = button.dataset.source;
    });
  });

  function renderTelemetrySummary(summary) {
    document.getElementById('total-prompts').textContent = summary.total_prompts || 0;
    document.getElementById('total-response').textContent = summary.total_response || 0;
    document.getElementById('total-errors').textContent = summary.total_errors || 0;
    document.getElementById('total-input-tokens').textContent = summary.total_input_tokens || 0;
    document.getElementById('total-output-tokens').textContent = summary.total_output_tokens || 0;
    const filter = document.getElementById('telemetry-model-filter');
    const current = filter.value;
    filter.innerHTML = '<option>All Models</option>' + (summary.models || []).map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`).join('');
    if ((summary.models || []).includes(current)) filter.value = current;
    renderTelemetryCharts(summary.series || []);
  }

  function renderTelemetryCharts(series) {
    const charts = [
      { id: 'throughput-chart', keys: ['prompts', 'responses', 'errors'], colors: ['#3c66f5', '#168d58', '#d64545'] },
      { id: 'token-chart', keys: ['input_tokens', 'output_tokens'], colors: ['#d77a00', '#7a4ed8'] },
    ];
    charts.forEach((chart) => {
      const container = document.getElementById(chart.id);
      if (!container) return;
      if (!series.length) {
        container.textContent = 'No telemetry yet';
        return;
      }
      const width = 520;
      const height = 180;
      const max = Math.max(1, ...series.flatMap((point) => chart.keys.map((key) => point[key] || 0)));
      const polylines = chart.keys.map((key, index) => {
        const points = series.map((point, pointIndex) => `${(pointIndex / Math.max(1, series.length - 1)) * width},${height - ((point[key] || 0) / max) * (height - 20)}`).join(' ');
        return `<polyline points="${points}" fill="none" stroke="${chart.colors[index]}" stroke-width="3" />`;
      }).join('');
      container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Telemetry line chart" preserveAspectRatio="none"><line x1="0" y1="${height - 1}" x2="${width}" y2="${height - 1}" stroke="#dfe5f1" />${polylines}</svg>`;
    });
  }

  function renderAuditSummary(summary) {
    document.getElementById('audit-prompts').textContent = summary.total_user_prompts || 0;
    document.getElementById('audit-model-calls').textContent = summary.model_calls || 0;
    document.getElementById('audit-embeds').textContent = summary.ollama_embeds || 0;
    document.getElementById('audit-latency').textContent = summary.avg_call_latency || '0ms';
  }

  function renderConversations(conversations) {
    const tbody = document.getElementById('conversation-table-body');
    if (!tbody) return;
    tbody.innerHTML = conversations.length
      ? conversations.map((row, index) => `
          <tr class="${index === 0 ? 'selected' : ''}" data-conversation="${row.conversation_id}">
            <td>${row.timestamp || 'n/a'}</td>
            <td>${row.conversation_id}</td>
            <td>${String(row.user_query || '').slice(0, 40)}</td>
            <td>${String(row.agent_response || '').slice(0, 80) || 'No response'}</td>
            <td>${row.agent_type || 'Custom Agent'}</td>
            <td>${row.event_count || 0}</td>
          </tr>
        `).join('')
      : '<tr><td colspan="6">No conversations</td></tr>';

    tbody.querySelectorAll('tr[data-conversation]').forEach((row) => {
      row.addEventListener('click', () => {
        tbody.querySelectorAll('tr').forEach((item) => item.classList.remove('selected'));
        row.classList.add('selected');
        renderConversationEvents(row.dataset.conversation);
      });
    });

    if (conversations.length) renderConversationEvents(conversations[0].conversation_id);
  }

  function renderEvents(events, conversationId) {
    const tbody = document.getElementById('event-table-body');
    const title = document.getElementById('event-table-title');
    if (!tbody || !title) return;
    title.textContent = `Events for Conversation ${conversationId || ''}`.trim();
    tbody.innerHTML = events.length
      ? events.map((event) => `
          <tr class="event-row">
            <td>${event.timestamp || 'n/a'}</td>
            <td>${event.event_type || 'unknown'}</td>
            <td>${event.invoker || 'n/a'}</td>
            <td>${event.target || 'n/a'}</td>
            <td>${event.description || ''}</td>
          </tr>
        `).join('')
      : '<tr><td colspan="5">No events for this conversation</td></tr>';

    tbody.querySelectorAll('.event-row').forEach((row, index) => {
      row.addEventListener('click', () => openEventDetails(events[index]));
    });
  }

  function openEventDetails(event) {
    const modal = document.getElementById('event-detail-modal');
    const title = document.getElementById('event-detail-title');
    const content = document.getElementById('event-detail-content');
    if (!modal || !title || !content) return;
    title.textContent = `${event.event_type || 'Event'} details`;
    content.textContent = JSON.stringify(event, null, 2);
    modal.classList.remove('hidden');
  }

  async function renderConversationEvents(conversationId) {
    try {
      const response = await fetch(`/api/audit/events?conversation_id=${encodeURIComponent(conversationId)}`);
      const data = await response.json();
      renderEvents(data.events || [], conversationId);
    } catch (error) {
      renderEvents([], conversationId);
    }
  }

  async function refreshDashboard() {
    try {
      const telemetry = await fetch('/api/telemetry').then((res) => res.json());
      renderTelemetrySummary(telemetry);
      const audit = await fetch('/api/audit').then((res) => res.json());
      renderAuditSummary(audit);
      renderConversations(audit.conversations || []);
    } catch (error) {
      // no-op for missing telemetry
    }
  }

  document.getElementById('refresh-telemetry-btn').addEventListener('click', refreshDashboard);
  document.getElementById('telemetry-model-filter').addEventListener('change', async (event) => {
    const telemetry = await fetch(`/api/telemetry?model=${encodeURIComponent(event.target.value)}`).then((res) => res.json());
    renderTelemetrySummary(telemetry);
  });
  document.getElementById('aggregation-select').addEventListener('change', refreshDashboard);
  document.getElementById('time-range-select').addEventListener('change', refreshDashboard);

  async function refreshHealth() {
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      const label = document.getElementById('backend-status-label');
      const dot = document.querySelector('.status-dot');
      if (data.status === 'ok') {
        label.textContent = `Backend Agent: ${data.agent || 'Online'} | ${data.services.join(', ')}`;
        dot.className = 'status-dot live';
      } else {
        label.textContent = 'Backend Agent: Offline';
        dot.className = 'status-dot offline';
      }
    } catch (error) {
      document.getElementById('backend-status-label').textContent = 'Backend Agent: Offline';
      document.querySelector('.status-dot').className = 'status-dot offline';
    }
  }

  async function refreshStats() {
    try {
      const stats = await fetch('/api/vector/stats').then((res) => res.json());
      document.getElementById('stat-chunks').textContent = stats.chunks || 0;
      document.getElementById('stat-docs').textContent = stats.documents || 0;
      document.getElementById('stat-mb').textContent = stats.size_mb || 0;
    } catch (error) {
      // ignore stats errors for UI bootstrap
    }
  }

  async function refreshModels() {
    try {
      const response = await fetch('/api/models');
      const data = await response.json();
      const select = document.getElementById('model-select');
      const models = data.models || [];
      if (!select || !models.length || models[0] === 'No generation model configured') return;
      const current = select.value;
      select.innerHTML = models.map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`).join('') + '<option value="Custom model">Custom model</option>';
      if (models.includes(current)) select.value = current;
    } catch (error) {
      // Keep the server-rendered default when model discovery is unavailable.
    }
  }

  async function refreshSkills() {
    try {
      const response = await fetch('/api/skills');
      const data = await response.json();
      const select = document.getElementById('skill-selector');
      if (!select) return;
      const options = select.querySelectorAll('option');
      const preserved = Array.from(options).slice(0, 2).map((option) => option.outerHTML).join('');
      select.innerHTML = preserved + (data.skills || []).map((skill) => `<option value="skill:${escapeHtml(skill.name)}">${escapeHtml(skill.name)}</option>`).join('');
    } catch (error) {
      // Keep the two built-in selectors when skill discovery is unavailable.
    }
  }

  function renderDocuments(documents) {
    const container = document.getElementById('storage-status');
    if (!container) return;
    if (!documents.length) {
      container.innerHTML = '<p class="empty-state">No documents ingested yet.</p>';
      return;
    }

    container.innerHTML = documents.map((document) => `
      <div class="document-row">
        <div class="document-details">
          <strong>${document.title || 'Untitled document'}</strong>
          <span>${document.chunks || 0} chunk${document.chunks === 1 ? '' : 's'} · ${document.chars || 0} characters</span>
          <small>${document.source || ''}</small>
        </div>
        <button class="danger-btn delete-document-btn" data-document-id="${document.id}" type="button">Delete</button>
      </div>
    `).join('');

    container.querySelectorAll('.delete-document-btn').forEach((button) => {
      button.addEventListener('click', async () => {
        const response = await fetch('/api/vector/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: button.dataset.documentId }),
        });
        if (response.ok) {
          refreshStats();
          refreshDocuments();
        }
      });
    });
  }

  async function refreshDocuments() {
    try {
      const response = await fetch('/api/vector/documents');
      const data = await response.json();
      renderDocuments(data.documents || []);
    } catch (error) {
      const container = document.getElementById('storage-status');
      if (container) container.innerHTML = '<p class="empty-state">Unable to load document status.</p>';
    }
  }

  refreshHealth();
  refreshStats();
  refreshModels();
  refreshSkills();
  refreshDocuments();
  refreshDashboard();
  setInterval(refreshHealth, 15000);
  setInterval(refreshStats, 20000);
  setInterval(refreshDashboard, 30000);
});

  document.getElementById('close-event-detail-btn').addEventListener('click', () => {
    document.getElementById('event-detail-modal').classList.add('hidden');
  });

  document.getElementById('event-detail-modal').addEventListener('click', (event) => {
    if (event.target.id === 'event-detail-modal') {
      event.currentTarget.classList.add('hidden');
    }
  });
