    const nodeIds = ["plan", "dispatch", "execute_task", "dispatch_reviews", "review_task", "update", "finalize"];
    const nodeIncomingEdges = {
      plan: ["edge-start-plan"],
      dispatch: ["edge-plan-dispatch", "edge-update-dispatch"],
      execute_task: ["edge-dispatch-execute"],
      dispatch_reviews: ["edge-execute-dispatch-reviews"],
      review_task: ["edge-dispatch-reviews-review"],
      update: ["edge-review-update"],
      finalize: ["edge-dispatch-finalize"]
    };
    let selectedRunId = window.MONITOR_BOOTSTRAP?.selectedRunId ?? null;
    let selectedConversationId = null;
    let pinnedConversation = false;
    let selectedNodeId = null;
    let pinnedNode = false;
    let artifactView = null;
    let latestSnapshot = null;
    let graphEdgeFrame = null;

    function escapeHtml(text) {
      return String(text ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    async function fetchJson(url, options) {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return await response.json();
    }

    function renderRuns(runs) {
      const container = document.getElementById("run-list");
      container.innerHTML = "";
      (runs || []).forEach((run) => {
        const div = document.createElement("div");
        div.className = "run-item" + (run.run_id === selectedRunId ? " active" : "");
        div.innerHTML = `<strong>${escapeHtml(run.run_id)}</strong><small>${escapeHtml(run.status)} · ${escapeHtml(run.created_at || "")}</small>`;
        div.onclick = async () => {
          selectedRunId = run.run_id;
          selectedConversationId = null;
          pinnedConversation = false;
          selectedNodeId = null;
          pinnedNode = false;
          artifactView = null;
          await refreshRuns();
          await refreshSnapshot();
        };
        container.appendChild(div);
      });
    }

    function chooseNode(nodeStatuses, latestNode) {
      if (pinnedNode && selectedNodeId && nodeStatuses[selectedNodeId]) {
        return;
      }
      selectedNodeId = latestNode || selectedNodeId || nodeIds.find((nodeId) => nodeStatuses[nodeId]) || "plan";
    }

    function renderNodeStatuses(nodeStatuses, latestNode) {
      chooseNode(nodeStatuses, latestNode);
      nodeIds.forEach((nodeId) => {
        const element = document.getElementById(`node-${nodeId}`);
        if (!element) return;
        element.className = "node "
          + ((nodeStatuses[nodeId] && nodeStatuses[nodeId].status) || "idle")
          + (selectedNodeId === nodeId ? " selected" : "");
      });

      const focusNode = selectedNodeId || latestNode;
      const activeEdges = new Set(nodeIncomingEdges[focusNode] || []);
      Object.keys(nodeIncomingEdges).flatMap((key) => nodeIncomingEdges[key]).forEach((edgeId) => {
        const edge = document.getElementById(edgeId);
        if (!edge) return;
        edge.classList.toggle("active", activeEdges.has(edgeId));
      });

      queueGraphEdgeUpdate();
    }

    function pointForAnchor(rect, anchor, containerRect) {
      if (anchor === "right") return { x: rect.right - containerRect.left, y: rect.top - containerRect.top + rect.height / 2 };
      if (anchor === "left") return { x: rect.left - containerRect.left, y: rect.top - containerRect.top + rect.height / 2 };
      if (anchor === "bottom") return { x: rect.left - containerRect.left + rect.width / 2, y: rect.bottom - containerRect.top };
      return { x: rect.left - containerRect.left + rect.width / 2, y: rect.top - containerRect.top };
    }

    function buildEdgePath(fromPoint, toPoint, shape) {
      if (shape === "loop-right") {
        const rightLane = Math.max(fromPoint.x, toPoint.x) + 140;
        return `M ${fromPoint.x} ${fromPoint.y} L ${rightLane} ${fromPoint.y} L ${rightLane} ${toPoint.y} L ${toPoint.x} ${toPoint.y}`;
      }
      if (shape === "elbow") {
        const midY = fromPoint.y + (toPoint.y - fromPoint.y) / 2;
        return `M ${fromPoint.x} ${fromPoint.y} L ${fromPoint.x} ${midY} L ${toPoint.x} ${midY} L ${toPoint.x} ${toPoint.y}`;
      }
      return `M ${fromPoint.x} ${fromPoint.y} L ${toPoint.x} ${toPoint.y}`;
    }

    function updateGraphEdges() {
      const graphCard = document.querySelector(".graph-card");
      const svg = document.querySelector(".graph-svg");
      if (!graphCard || !svg) return;

      const graphRect = graphCard.getBoundingClientRect();
      svg.setAttribute("viewBox", `0 0 ${graphRect.width} ${graphRect.height}`);

      document.querySelectorAll(".edge[data-from]").forEach((edge) => {
        const fromNode = document.getElementById(edge.dataset.from);
        const toNode = document.getElementById(edge.dataset.to);
        if (!fromNode || !toNode) return;
        const fromRect = fromNode.getBoundingClientRect();
        const toRect = toNode.getBoundingClientRect();
        const fromPoint = pointForAnchor(fromRect, edge.dataset.fromAnchor || "right", graphRect);
        const toPoint = pointForAnchor(toRect, edge.dataset.toAnchor || "left", graphRect);
        edge.setAttribute("d", buildEdgePath(fromPoint, toPoint, edge.dataset.shape || "line"));
      });
    }

    function queueGraphEdgeUpdate() {
      if (graphEdgeFrame) cancelAnimationFrame(graphEdgeFrame);
      graphEdgeFrame = requestAnimationFrame(() => {
        updateGraphEdges();
        graphEdgeFrame = null;
      });
    }

    function findConversationId(conversations, taskId, agent) {
      const match = (conversations || []).find((conversation) => conversation.task_id === taskId && conversation.agent === agent);
      return match ? match.id : null;
    }

    function syntheticNodeConversation(snapshot, nodeId) {
      const detail = snapshot?.node_details?.[nodeId];
      if (!detail) return null;
      const eventLines = (detail.recent_events || []).map((event) => {
        const task = event.task_id ? ` · task=${event.task_id}` : "";
        const batch = event.batch_id ? ` · batch=${event.batch_id}` : "";
        return `${event.timestamp} · ${event.phase}${task}${batch}`;
      }).join("\\n");
      return {
        id: `node:${nodeId}`,
        title: `${nodeId} agent`,
        agent: "node-agent",
        node: nodeId,
        task_id: null,
        status: detail.status || "idle",
        messages: [
          {
            role: "system",
            label: "Node State",
            content: `status=${detail.status}\nlatest_phase=${detail.latest_phase}\nrun_count=${detail.run_count}\nopen_traces=${(detail.open_traces || []).length}\ntasks=${(detail.tasks || []).join(", ") || "-" }\nbatches=${(detail.batches || []).join(", ") || "-" }`,
          },
          {
            role: "assistant",
            label: "Recent Events",
            content: eventLines || "No recent events.",
          },
        ],
      };
    }

    function conversationsForSelection(snapshot) {
      const allConversations = snapshot?.conversations || [];
      if (!selectedNodeId) return allConversations;
      const related = allConversations.filter((conversation) => conversation.node === selectedNodeId);
      const synthetic = syntheticNodeConversation(snapshot, selectedNodeId);
      return synthetic ? [synthetic, ...related] : related;
    }

    function renderTasks(tasks, conversations) {
      const container = document.getElementById("task-list");
      container.innerHTML = "";
      (tasks || []).forEach((task) => {
        const div = document.createElement("div");
        div.className = "task";
        const executeId = findConversationId(conversations, task.task_id, "executor");
        const reviewId = findConversationId(conversations, task.task_id, "reviewer");
        div.innerHTML = `
          <strong>${escapeHtml(task.task_id)}</strong>
          <div class="muted" style="margin-top: 6px;">status=${escapeHtml(task.status)} · retries=${escapeHtml(task.retries ?? 0)}</div>
          <div class="task-buttons">
            ${executeId ? `<button class="mini-button" data-thread="${escapeHtml(executeId)}">executor</button>` : ""}
            ${reviewId ? `<button class="mini-button" data-thread="${escapeHtml(reviewId)}">reviewer</button>` : ""}
          </div>
        `;
        div.querySelectorAll("[data-thread]").forEach((button) => {
          button.onclick = () => {
            selectedConversationId = button.getAttribute("data-thread");
            pinnedConversation = true;
            selectedNodeId = task.task_id && button.textContent === "reviewer" ? "review_task" : "execute_task";
            pinnedNode = true;
            artifactView = null;
            renderThreadView(latestSnapshot);
            renderThreads(latestSnapshot, latestSnapshot?.latest_conversation_id || null);
            renderNodeStatuses(latestSnapshot?.node_statuses || {}, latestSnapshot?.latest?.node || "");
            renderNodeDetail(latestSnapshot);
          };
        });
        container.appendChild(div);
      });
      if (!container.innerHTML) {
        container.innerHTML = '<div class="empty">暂无 task。</div>';
      }
    }

    function renderBatches(batches) {
      const container = document.getElementById("batch-list");
      container.innerHTML = "";
      (batches || []).forEach((batch) => {
        const div = document.createElement("div");
        div.className = "batch";
        const chips = (batch.task_ids || []).map((taskId) => `<span class="chip">${escapeHtml(taskId)}</span>`).join("");
        div.innerHTML = `<strong>${escapeHtml(batch.batch_id)}</strong><div>${chips}</div><div class="muted" style="margin-top: 8px;">${escapeHtml((batch.nodes || []).join(" → "))}</div>`;
        container.appendChild(div);
      });
      if (!container.innerHTML) {
        container.innerHTML = '<div class="empty">暂无 batch。</div>';
      }
    }

    async function openArtifact(path) {
      if (!selectedRunId || !path) return;
      const data = await fetchJson(`/api/runs/${selectedRunId}/artifact?path=${encodeURIComponent(path)}`);
      artifactView = data;
      pinnedConversation = true;
      renderThreadView(latestSnapshot);
      renderThreads(latestSnapshot, latestSnapshot?.latest_conversation_id || null);
    }

    function renderArtifacts(artifacts, logPath) {
      const container = document.getElementById("artifact-list");
      container.innerHTML = "";
      const items = [...(artifacts || [])];
      if (logPath) items.push(logPath);

      items.forEach((artifactPath) => {
        const button = document.createElement("button");
        button.className = "artifact-item";
        button.style.width = "100%";
        button.style.textAlign = "left";
        button.style.background = "var(--panel-2)";
        button.style.color = "var(--ink)";
        button.style.marginTop = "0";
        button.textContent = artifactPath.split("/").slice(-2).join("/");
        button.onclick = () => openArtifact(artifactPath);
        container.appendChild(button);
      });

      if (!container.innerHTML) {
        container.innerHTML = '<div class="empty">暂无 artifact。</div>';
      }
    }

    function renderTimeline(events) {
      const container = document.getElementById("timeline");
      container.innerHTML = "";
      const filteredEvents = selectedNodeId
        ? (events || []).filter((event) => event.node === selectedNodeId)
        : (events || []);
      filteredEvents.slice(-24).reverse().forEach((event) => {
        const li = document.createElement("li");
        const payloadTask = event.payload?.task_id ? ` · ${escapeHtml(event.payload.task_id)}` : "";
        li.innerHTML = `<code>${escapeHtml(event.timestamp)}</code><br><strong>${escapeHtml(event.node)}</strong> · ${escapeHtml(event.phase)}${payloadTask}`;
        container.appendChild(li);
      });
      if (!container.innerHTML) {
        container.innerHTML = '<li>暂无 timeline。</li>';
      }
    }

    function chooseConversation(conversations, suggestedId) {
      const availableIds = new Set((conversations || []).map((conversation) => conversation.id));
      if (artifactView) return;
      if (selectedConversationId && availableIds.has(selectedConversationId) && pinnedConversation) return;
      if (selectedNodeId && availableIds.has(`node:${selectedNodeId}`)) {
        selectedConversationId = `node:${selectedNodeId}`;
        return;
      }
      if (suggestedId && availableIds.has(suggestedId)) {
        selectedConversationId = suggestedId;
        return;
      }
      if (!selectedConversationId || !availableIds.has(selectedConversationId)) {
        selectedConversationId = conversations?.[0]?.id || null;
      }
    }

    function renderThreads(snapshot, suggestedId) {
      const conversations = conversationsForSelection(snapshot);
      chooseConversation(conversations, suggestedId);
      const container = document.getElementById("thread-list");
      container.innerHTML = "";
      (conversations || []).forEach((conversation) => {
        const div = document.createElement("div");
        div.className = "thread-item" + (conversation.id === selectedConversationId && !artifactView ? " active" : "");
        div.innerHTML = `
          <strong>${escapeHtml(conversation.title)}</strong>
          <small>${escapeHtml(conversation.agent)}${conversation.task_id ? ` · ${escapeHtml(conversation.task_id)}` : ""} · ${escapeHtml(conversation.status || "-")}</small>
        `;
        div.onclick = () => {
          selectedConversationId = conversation.id;
          pinnedConversation = true;
          artifactView = null;
          renderThreadView(latestSnapshot);
          renderThreads(latestSnapshot, latestSnapshot?.latest_conversation_id || null);
        };
        container.appendChild(div);
      });
      if (!container.innerHTML) {
        container.innerHTML = '<div class="empty">暂无 agent thread。</div>';
      }
    }

    function renderThreadView(snapshot) {
      const meta = document.getElementById("thread-meta");
      const log = document.getElementById("chat-log");
      const badge = document.getElementById("console-badge");

      if (artifactView) {
        badge.textContent = "thread: artifact";
        meta.innerHTML = `<strong>${escapeHtml(artifactView.path.split("/").slice(-2).join("/"))}</strong><div class="muted" style="margin-top:6px;">Artifact Viewer</div>`;
        log.innerHTML = `<div class="message system"><div class="message-label">artifact</div><div class="bubble">${escapeHtml(artifactView.content)}</div></div>`;
        return;
      }

      const conversation = conversationsForSelection(snapshot).find((item) => item.id === selectedConversationId);
      if (!conversation) {
        badge.textContent = "thread: -";
        meta.innerHTML = `<strong>未选择线程</strong><div class="muted" style="margin-top:6px;">运行后这里会显示对应 agent 的 prompt、结果和 artifact 内容。</div>`;
        log.innerHTML = '<div class="empty">暂无可显示的上下文。</div>';
        return;
      }

      badge.textContent = `thread: ${conversation.title}`;
      meta.innerHTML = `
        <strong>${escapeHtml(conversation.title)}</strong>
        <div class="muted" style="margin-top:6px;">agent=${escapeHtml(conversation.agent)} · node=${escapeHtml(conversation.node)}${conversation.task_id ? ` · task=${escapeHtml(conversation.task_id)}` : ""} · status=${escapeHtml(conversation.status || "-")}</div>
      `;
      const diagnosticsBlock = conversation.diagnostics ? `
        <details class="diagnostics">
          <summary>Diagnostics</summary>
          <pre>${escapeHtml(conversation.diagnostics)}</pre>
        </details>
      ` : "";
      log.innerHTML = ((conversation.messages || []).map((message) => `
        <div class="message ${escapeHtml(message.role || "assistant")}">
          <div class="message-label">${escapeHtml(message.label || message.role || "message")}</div>
          <div class="bubble">${escapeHtml(message.content || "")}</div>
        </div>
      `).join("") || '<div class="empty">这个线程还没有内容。</div>') + diagnosticsBlock;
      log.scrollTop = 0;
    }

    function renderNodeDetail(snapshot) {
      const detail = snapshot?.node_details?.[selectedNodeId || ""];
      document.getElementById("selected-node").textContent = selectedNodeId || "-";
      document.getElementById("selected-node-status").textContent = detail?.status || "-";
      document.getElementById("selected-node-phase").textContent = detail?.latest_phase || "-";
      document.getElementById("selected-node-runs").textContent = detail ? String(detail.run_count ?? 0) : "-";

      const tagBox = document.getElementById("selected-node-tags");
      tagBox.innerHTML = "";
      (detail?.tasks || []).forEach((taskId) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = taskId;
        tagBox.appendChild(chip);
      });
      (detail?.batches || []).forEach((batchId) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = batchId;
        tagBox.appendChild(chip);
      });
      if (!tagBox.innerHTML) {
        tagBox.innerHTML = '<div class="muted" style="margin: 4px 0 0;">No related tasks or batches.</div>';
      }

      const eventsBox = document.getElementById("selected-node-events");
      eventsBox.innerHTML = "";
      (detail?.recent_events || []).slice().reverse().forEach((event) => {
        const row = document.createElement("div");
        row.innerHTML = `<code>${escapeHtml(event.timestamp)}</code> · <strong>${escapeHtml(event.phase)}</strong>${event.task_id ? ` · ${escapeHtml(event.task_id)}` : ""}${event.batch_id ? ` · ${escapeHtml(event.batch_id)}` : ""}`;
        eventsBox.appendChild(row);
      });
      if (!eventsBox.innerHTML) {
        eventsBox.innerHTML = "<div>点击 graph 中的节点后，这里会显示该节点最近的运行事件。</div>";
      }
    }

    async function refreshRuns() {
      const data = await fetchJson("/api/runs");
      renderRuns(data.runs || []);
      if (!selectedRunId && data.runs && data.runs.length > 0) {
        selectedRunId = data.runs[0].run_id;
      }
    }

    async function refreshSnapshot() {
      if (!selectedRunId) return;
      const snapshot = await fetchJson(`/api/runs/${selectedRunId}/snapshot`);
      latestSnapshot = snapshot;

      document.getElementById("run-id").textContent = snapshot.run?.run_id || selectedRunId;
      document.getElementById("run-status").textContent = snapshot.run?.status || "-";
      document.getElementById("latest-node").textContent = snapshot.latest?.node || "-";
      document.getElementById("latest-phase").textContent = snapshot.latest?.phase || "-";
      document.getElementById("latest-task").textContent = snapshot.latest?.state?.current_task_id || snapshot.latest?.payload?.task_id || "-";
      document.getElementById("final-status").textContent = snapshot.latest_state?.final_status || snapshot.summary?.final_status || "-";
      document.getElementById("graph-run-badge").textContent = `run: ${snapshot.run?.run_id || "-"}`;
      document.getElementById("graph-node-badge").textContent = `node: ${snapshot.latest?.node || "-"}`;
      document.getElementById("graph-phase-badge").textContent = `phase: ${snapshot.latest?.phase || "-"}`;

      renderNodeStatuses(snapshot.node_statuses || {}, snapshot.latest?.node || "");
      renderNodeDetail(snapshot);
      renderTasks(snapshot.tasks || [], snapshot.conversations || []);
      renderBatches(snapshot.batches || []);
      renderArtifacts(snapshot.artifacts || [], snapshot.process_log_path);
      renderTimeline(snapshot.events || []);
      renderThreads(snapshot, snapshot.latest_conversation_id || null);
      renderThreadView(snapshot);
      queueGraphEdgeUpdate();
    }

    document.getElementById("start-run").onclick = async () => {
      const prompt = document.getElementById("prompt-input").value;
      const data = await fetchJson("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
      });
      selectedRunId = data.run_id;
      selectedConversationId = null;
      pinnedConversation = false;
      selectedNodeId = null;
      pinnedNode = false;
      artifactView = null;
      await refreshRuns();
      await refreshSnapshot();
    };

    async function boot() {
      nodeIds.forEach((nodeId) => {
        const node = document.getElementById(`node-${nodeId}`);
        if (!node) return;
        node.onclick = () => {
          selectedNodeId = nodeId;
          pinnedNode = true;
          selectedConversationId = null;
          pinnedConversation = false;
          artifactView = null;
          renderNodeStatuses(latestSnapshot?.node_statuses || {}, latestSnapshot?.latest?.node || "");
          renderNodeDetail(latestSnapshot);
          renderTimeline(latestSnapshot?.events || []);
          renderThreads(latestSnapshot, latestSnapshot?.latest_conversation_id || null);
          renderThreadView(latestSnapshot);
        };
      });
      await refreshRuns();
      await refreshSnapshot();
      queueGraphEdgeUpdate();
      setTimeout(queueGraphEdgeUpdate, 0);
      window.addEventListener("resize", queueGraphEdgeUpdate);
      setInterval(refreshRuns, 2000);
      setInterval(refreshSnapshot, 1000);
    }
    boot();
  
