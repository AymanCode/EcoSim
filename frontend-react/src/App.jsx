import React, { useState, useEffect, useRef } from 'react';
import Markets from './screens/Markets.jsx';
import Government from './screens/Government.jsx';
import Rail from './shell/Rail.jsx';
import TopBar from './shell/TopBar.jsx';
import StatusStrip from './shell/StatusStrip.jsx';
import Command from './screens/Command.jsx';
import Population from './screens/Population.jsx';
import Finance from './screens/Finance.jsx';
import Logs from './screens/Logs.jsx';
import Config from './screens/Config.jsx';
import { useTickHistory, stress } from './telemetry.js';

const resolveWebSocketEndpoint = () => {
  const configuredEndpoint = (import.meta.env.VITE_WS_URL || '').trim();
  if (configuredEndpoint) {
    return configuredEndpoint;
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}/ws`;
  }

  return 'ws://localhost:8002/ws';
};



// --- REUSABLE CHART COMPONENT ---
export default function EcoSimUI() {
  const wsEndpoint = resolveWebSocketEndpoint();
  const [activeView, setActiveView] = useState('CONFIG'); // Start at CONFIG
  const [isInitialized, setIsInitialized] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [tick, setTick] = useState(0);
  const [logs, setLogs] = useState([]);
  const ws = useRef(null);
  const reconnectTimerRef = useRef(null);
  const configUpdateTimer = useRef(null);
  const pendingConfigRef = useRef(null);
  const sentConfigRef = useRef(null);
  const [isInitializing, setIsInitializing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('ecosim.theme') || 'ember';
    } catch {
      return 'ember';
    }
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('ecosim.theme', theme);
    } catch {
      // Ignore storage errors (e.g. private browsing, disabled storage).
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'ember' ? 'paper' : 'ember'));
  };

  // Simulation State
  const [metrics, setMetrics] = useState({
    unemployment: 99.0,
    gdp: 0.0,
    govDebt: 0.0,
    govProfit: 0.0,
    happiness: 50,
    housingInv: 0,
    avgWage: 0.0,
    avgExpectedWage: 0.0,
    avgExpectedWageUnemployed: 0.0,
    giniCoefficient: 0.0,
    top10Share: 0.0,
    bottom50Share: 0.0,
    gdpHistory: [],
    unemploymentHistory: [],
    wageHistory: [],
    medianWageHistory: [],
    happinessHistory: [],
    healthHistory: [],
    govProfitHistory: [],
    govDebtHistory: [],
    firmCountHistory: [],
    giniHistory: [],
    top10ShareHistory: [],
    bottom50ShareHistory: [],
    priceHistory: { food: [], housing: [], services: [], healthcare: [] },
    supplyHistory: { food: [], housing: [], services: [], healthcare: [] },
    trackedSubjects: [],
    trackedFirms: [],
    policyChanges: [],
    latestGovernmentDecision: null,
    llmGovernment: { enabled: false, status: 'disabled', latestDecision: null },
    governmentPolicy: {}
  });

  const [requestedSubjectIndex, setActiveSubjectIndex] = useState(0);
  const [requestedFirmIndex, setActiveFirmIndex] = useState(0);
  const [firmStats, setFirmStats] = useState(null);
  const [subjectSearch, setSubjectSearch] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('All');
  const [logSearch, setLogSearch] = useState('');
  const [logTypeFilter, setLogTypeFilter] = useState('All');
  const [logSeverityFilter, setLogSeverityFilter] = useState('All');
  const [selectedLogId, setSelectedLogId] = useState(null);
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const [logDensity, setLogDensity] = useState('comfortable');

  const [config, setConfig] = useState({
    wageTax: 0.05,
    profitTax: 0.30,
    inflationRate: 0.02,
    birthRate: 0.01,
    minimumWage: 20.0,
    unemploymentBenefitRate: 0.0,
    universalBasicIncome: 0.0,
    wealthTaxThreshold: 50000,
    wealthTaxRate: 0.0,
    enableLlmGovernment: false,
    benefitLevel: 'neutral',
    publicWorks: false,
    minimumWagePolicy: 'neutral',
    sectorSubsidyTarget: 'none',
    sectorSubsidyLevel: 0,
    infrastructureSpending: 'none',
    technologySpending: 'none',
    socialSpending: 'medium',
    priceStabilizationTarget: 'none',
    priceStabilizationLevel: 'off',
    rentStabilizationLevel: 'off',
    bailoutPolicy: 'off',
    bailoutTarget: 'none',
    bailoutBudget: 0
  });

  // Setup State (for initialization)
  const [setupConfig, setSetupConfig] = useState({
    num_households: 1000,
    num_firms: 5,
    seed: 42,
    wage_tax: 0.15,
    profit_tax: 0.20,
    enable_llm_government: false,
    disable_stabilizers: false,
    disabled_agents: []
  });
  const setupConfigRef = useRef(setupConfig);
  useEffect(() => {
    setupConfigRef.current = setupConfig;
  }, [setupConfig]);
  const stabilizerAgentOptions = [
    { key: 'households', label: 'Households' },
    { key: 'firms', label: 'Firms' },
    { key: 'government', label: 'Government' },
    { key: 'all', label: 'All Agents' }
  ];
  const subjectCount = metrics.trackedSubjects ? metrics.trackedSubjects.length : 0;
  const firmCount = metrics.trackedFirms ? metrics.trackedFirms.length : 0;
  const activeSubjectIndex = subjectCount > 0 && requestedSubjectIndex < subjectCount ? requestedSubjectIndex : 0;
  const activeFirmIndex = firmCount > 0 && requestedFirmIndex < firmCount ? requestedFirmIndex : 0;




  useEffect(() => {
    return () => {
      if (configUpdateTimer.current) {
        clearTimeout(configUpdateTimer.current);
      }
    };
  }, []);

  // WebSocket Connection (with auto-reconnect)
  useEffect(() => {
    let cancelled = false;
    let effectSocket = null;

    const connect = () => {
      if (cancelled) return;
      const socket = new WebSocket(wsEndpoint);
      ws.current = socket;
      effectSocket = socket;

      socket.onopen = () => {
        if (cancelled || ws.current !== socket) return;
        setWsConnected(true);
        console.log("WS Connected");
      };

      socket.onmessage = (event) => {
        if (cancelled || ws.current !== socket) return;
        const data = JSON.parse(event.data);
        if (data.type === "SESSION") {
          setSessionId(data.sessionId || '');
        } else if (data.type === "SETUP_COMPLETE") {
          setIsInitializing(false);
          setIsInitialized(true);
          setActiveView('DASHBOARD');
          setIsRunning(true);
          const cfg = setupConfigRef.current;
          // Sync local config with setup
          setConfig(prev => {
            const synced = {
              ...prev,
              wageTax: cfg.wage_tax,
              profitTax: cfg.profit_tax,
              enableLlmGovernment: cfg.enable_llm_government !== false
            };
            // Baseline for runtime CONFIG diffs: the server logs every key it
            // receives as a user policy change, so only changed keys are sent.
            sentConfigRef.current = synced;
            return synced;
          });
          // Add boot sequence logs
          setLogs([
            { tick: 0, type: 'SYS', txt: 'INITIALIZING KERNEL...' },
            { tick: 0, type: 'SYS', txt: 'LOADING CONFIGURATION MAP...' },
            { tick: 0, type: 'SYS', txt: `SPAWNING ${cfg.num_households} AGENTS...` },
            { tick: 0, type: 'ECO', txt: 'WARMUP PHASE STARTED' }
          ]);
          // Auto-start simulation after setup
          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ command: "START" }));
          }
        } else if (data.type === "RESET") {
          setTick(0);
          setLogs([]);
          setMetrics({
            unemployment: 99.0,
            gdp: 0,
            govDebt: 0,
            govProfit: 0,
            happiness: 50,
            housingInv: 0,
            avgWage: 0,
            avgExpectedWage: 0.0,
            avgExpectedWageUnemployed: 0.0,
            giniCoefficient: 0.0,
            top10Share: 0.0,
            bottom50Share: 0.0,
            gdpHistory: [],
            unemploymentHistory: [],
            wageHistory: [],
            medianWageHistory: [],
            happinessHistory: [],
            healthHistory: [],
            govProfitHistory: [],
            govDebtHistory: [],
            giniHistory: [],
            top10ShareHistory: [],
            bottom50ShareHistory: [],
            housingHistory: [],
            foodHistory: [],
            servicesHistory: [],
            priceHistory: { food: [], housing: [], services: [], healthcare: [] },
            supplyHistory: { food: [], housing: [], services: [], healthcare: [] },
            trackedSubjects: [],
            trackedFirms: [],
            policyChanges: [],
            latestGovernmentDecision: null,
            llmGovernment: { enabled: false, status: 'disabled', latestDecision: null },
            governmentPolicy: {}
          });
          setActiveSubjectIndex(0);
          setActiveFirmIndex(0);
          setFirmStats(null);
          setIsRunning(false);
          setIsInitialized(false);
          setActiveView('CONFIG'); // Go back to config on reset
        } else if (data.type === "STABILIZERS_UPDATED") {
          console.log("Stabilizers updated:", data.state);
        } else if (data.type === "STARTED") {
          setIsRunning(true);
        } else if (data.type === "STOPPED") {
          setIsRunning(false);
        } else if (data.metrics) {
          setTick(data.tick);
          // Merge with existing metrics to preserve defaults if backend is missing keys
          setMetrics(prev => ({
            ...prev,
            ...data.metrics,
            // Ensure nested objects/arrays are not overwritten with undefined if missing
            priceHistory: data.metrics.priceHistory || prev.priceHistory || { food: [], housing: [], services: [], healthcare: [] },
            supplyHistory: data.metrics.supplyHistory || prev.supplyHistory || { food: [], housing: [], services: [], healthcare: [] },
            netWorthHistory: data.metrics.netWorthHistory || prev.netWorthHistory || [],
            trackedSubjects: data.metrics.trackedSubjects || prev.trackedSubjects || [],
            trackedFirms: data.metrics.trackedFirms || prev.trackedFirms || []
          }));
          if (data.firm_stats) {
            setFirmStats(data.firm_stats);
          }
          if (data.logs && data.logs.length > 0) {
            setLogs(prev => [...prev.slice(-300), ...data.logs]);
          }
        } else if (data.error) {
          console.error("Simulation error:", data.error);
          setIsInitializing(false);
        }
      };

      socket.onclose = () => {
        if (ws.current !== socket) return;
        setWsConnected(false);
        setSessionId('');
        console.log("WS Disconnected");
        setIsRunning(false);
        setIsInitializing(false);
        if (!cancelled) {
          reconnectTimerRef.current = setTimeout(connect, 1200);
        }
      };

      socket.onerror = (err) => {
        if (cancelled || ws.current !== socket) return;
        console.error("WebSocket error:", err);
        setIsInitializing(false);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (effectSocket) {
        effectSocket.close();
      }
    };
  }, [wsEndpoint]);

  const handleInitialize = () => {
    if (setupConfig.num_households < 1 || setupConfig.num_firms < 1 || setupConfig.seed < 0) {
      console.error("Invalid setup config. num_households and num_firms must be >= 1; seed must be >= 0.");
      return;
    }
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setIsInitializing(true);
      ws.current.send(JSON.stringify({
        command: "SETUP",
        config: setupConfig
      }));
    } else {
      console.error("WebSocket is not connected. Cannot initialize.");
    }
  };

  const toggleRun = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      if (isRunning) {
        ws.current.send(JSON.stringify({ command: "STOP" }));
      } else {
        ws.current.send(JSON.stringify({ command: "START" }));
      }
      // Don't update state here - wait for backend confirmation
    }
  };

  const handleReset = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ command: "RESET" }));
    }
  };

  const flushConfigUpdates = () => {
    if (
      pendingConfigRef.current &&
      ws.current &&
      ws.current.readyState === WebSocket.OPEN &&
      isInitialized
    ) {
      const supportedRuntimeConfig = {
        wageTax: pendingConfigRef.current.wageTax,
        profitTax: pendingConfigRef.current.profitTax,
        minimumWage: pendingConfigRef.current.minimumWage,
        unemploymentBenefitRate: pendingConfigRef.current.unemploymentBenefitRate,
        enableLlmGovernment: pendingConfigRef.current.enableLlmGovernment,
        benefitLevel: pendingConfigRef.current.benefitLevel,
        publicWorks: pendingConfigRef.current.publicWorks,
        minimumWagePolicy: pendingConfigRef.current.minimumWagePolicy,
        sectorSubsidyTarget: pendingConfigRef.current.sectorSubsidyTarget,
        sectorSubsidyLevel: pendingConfigRef.current.sectorSubsidyLevel,
        infrastructureSpending: pendingConfigRef.current.infrastructureSpending,
        technologySpending: pendingConfigRef.current.technologySpending,
        socialSpending: pendingConfigRef.current.socialSpending,
        priceStabilizationTarget: pendingConfigRef.current.priceStabilizationTarget,
        priceStabilizationLevel: pendingConfigRef.current.priceStabilizationLevel,
        rentStabilizationLevel: pendingConfigRef.current.rentStabilizationLevel,
        bailoutPolicy: pendingConfigRef.current.bailoutPolicy,
        bailoutTarget: pendingConfigRef.current.bailoutTarget,
        bailoutBudget: pendingConfigRef.current.bailoutBudget,
      };
      const baseline = sentConfigRef.current;
      const changedConfig = baseline
        ? Object.fromEntries(Object.entries(supportedRuntimeConfig).filter(([key, value]) => !Object.is(baseline[key], value)))
        : supportedRuntimeConfig;
      if (Object.keys(changedConfig).length > 0) {
        ws.current.send(JSON.stringify({ command: "CONFIG", config: changedConfig }));
        sentConfigRef.current = { ...(baseline || {}), ...changedConfig };
      }
    }
    pendingConfigRef.current = null;
    configUpdateTimer.current = null;
  };

  const handleConfigChange = (key, value) => {
    const newConfig = { ...config, [key]: value };
    setConfig(newConfig);
    pendingConfigRef.current = newConfig;
    if (configUpdateTimer.current) {
      clearTimeout(configUpdateTimer.current);
    }
    configUpdateTimer.current = setTimeout(flushConfigUpdates, 400);
  };

  const resetPolicyDefaults = () => {
    const defaults = {
      wageTax: 0.15,
      profitTax: 0.20,
      minimumWage: 20,
      unemploymentBenefitRate: 0,
      enableLlmGovernment: false,
      benefitLevel: 'neutral',
      publicWorks: false,
      minimumWagePolicy: 'neutral',
      sectorSubsidyTarget: 'none',
      sectorSubsidyLevel: 0,
      infrastructureSpending: 'none',
      technologySpending: 'none',
      socialSpending: 'medium',
      priceStabilizationTarget: 'none',
      priceStabilizationLevel: 'off',
      rentStabilizationLevel: 'off',
      bailoutPolicy: 'off',
      bailoutTarget: 'none',
      bailoutBudget: 0
    };
    setConfig(prev => {
      const next = { ...prev, ...defaults };
      pendingConfigRef.current = next;
      if (configUpdateTimer.current) clearTimeout(configUpdateTimer.current);
      configUpdateTimer.current = setTimeout(flushConfigUpdates, 120);
      return next;
    });
    setSetupConfig(prev => ({
      ...prev,
      wage_tax: defaults.wageTax,
      profit_tax: defaults.profitTax,
      enable_llm_government: defaults.enableLlmGovernment,
      disable_stabilizers: false,
      disabled_agents: []
    }));
  };

  // Helper to update setup config
  const sendStabilizerCommand = (disableFlag, disabledAgents) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        command: "STABILIZERS",
        disable_stabilizers: disableFlag,
        disabled_agents: disabledAgents
      }));
    }
  };

  const handleSetupChange = (key, value) => {
    setSetupConfig(prev => {
      const next = { ...prev, [key]: value };
      if (key === 'disable_stabilizers' && value === false) {
        next.disabled_agents = [];
      }
      if (isInitialized && (key === 'disable_stabilizers' || key === 'disabled_agents')) {
        sendStabilizerCommand(next.disable_stabilizers, next.disabled_agents);
      }
      return next;
    });
    // Also update the runtime config preview
    if (key === 'wage_tax') setConfig(prev => ({ ...prev, wageTax: value }));
    if (key === 'profit_tax') setConfig(prev => ({ ...prev, profitTax: value }));
    if (key === 'enable_llm_government') setConfig(prev => ({ ...prev, enableLlmGovernment: value }));
  };

  const enumOptions = {
    level4: [
      { value: 'none', label: 'None' },
      { value: 'low', label: 'Low' },
      { value: 'medium', label: 'Medium' },
      { value: 'high', label: 'High' },
    ],
    sectors: [
      { value: 'none', label: 'None' },
      { value: 'food', label: 'Food' },
      { value: 'housing', label: 'Housing' },
      { value: 'services', label: 'Services' },
      { value: 'healthcare', label: 'Healthcare' },
    ],
    stabilization: [
      { value: 'off', label: 'Off' },
      { value: 'monitor', label: 'Monitor' },
      { value: 'soft', label: 'Soft' },
      { value: 'strict', label: 'Strict' },
    ],
    benefit: [
      { value: 'low', label: 'Low' },
      { value: 'neutral', label: 'Neutral' },
      { value: 'high', label: 'High' },
      { value: 'crisis', label: 'Crisis' },
    ],
    wagePolicy: [
      { value: 'low', label: 'Low' },
      { value: 'neutral', label: 'Neutral' },
      { value: 'high', label: 'High' },
    ],
    bailoutPolicy: [
      { value: 'off', label: 'Off' },
      { value: 'sector', label: 'Sector' },
      { value: 'all', label: 'All' },
    ],
    subsidyLevels: [
      { value: '0', label: '0%' },
      { value: '10', label: '10%' },
      { value: '25', label: '25%' },
      { value: '50', label: '50%' },
    ],
    bailoutBudgets: [
      { value: '0', label: '$0' },
      { value: '5000', label: '$5K' },
      { value: '10000', label: '$10K' },
      { value: '25000', label: '$25K' },
      { value: '50000', label: '$50K' },
    ],
  };

  const llmGov = metrics.llmGovernment || { status: 'disabled', latestDecision: null };
  const rawLatestDecision = llmGov.latestDecision || metrics.latestGovernmentDecision || null;
  const hasLatestDecisionContent = rawLatestDecision && Object.keys(rawLatestDecision).length > 0 && Boolean(
    rawLatestDecision.rationale
    || rawLatestDecision.reasoning
    || rawLatestDecision.decision_summary
    || rawLatestDecision.primary_goal
    || rawLatestDecision.status
    || rawLatestDecision.appliedTick
    || rawLatestDecision.snapshotTick
    || Object.keys(rawLatestDecision.decisions || rawLatestDecision.applied_changes || {}).length
    || (Array.isArray(rawLatestDecision.rejected_changes) && rawLatestDecision.rejected_changes.length)
  );
  const latestDecisionTick = rawLatestDecision
    ? Number(rawLatestDecision.appliedTick ?? rawLatestDecision.tick ?? rawLatestDecision.snapshotTick ?? 0)
    : 0;
  const latestDecision = hasLatestDecisionContent && rawLatestDecision && (!latestDecisionTick || latestDecisionTick <= Number(tick || 0))
    ? rawLatestDecision
    : null;
  const isPolicyAssistantActive = Boolean(config.enableLlmGovernment || setupConfig.enable_llm_government || llmGov.enabled);
  const llmStatusLabel = {
    disabled: 'Inactive',
    provider_unavailable: 'Policy assistant inactive',
    thinking: 'Policy evaluation running',
    ready: 'Policy assistant ready',
    applying: 'Applying policy',
    error: 'AI policy error'
  }[llmGov.status] || (isPolicyAssistantActive ? 'Policy assistant ready' : 'Inactive');
  const llmActivityLevel = llmGov.status === 'thinking' || llmGov.status === 'applying'
    ? 'high'
    : (metrics.govProfit || 0) < 0 ? 'high' : 'normal';
  const friendlyModelName = (() => {
    const raw = String(llmGov.model || llmGov.provider || 'Rule-based policy');
    const parts = raw.split('/');
    return parts[parts.length - 1] || raw;
  })();

  const stressVal = stress(metrics);
  const rev = Number(metrics.govRevenue || 0);
  const out = Number(metrics.govTransfers || 0) + Number(metrics.govInvestments || 0) + Number(metrics.bondPurchases || 0);
  const bonds = Number(metrics.bondPurchases || 0);
  const loans = Number(metrics.activeLoans || 0);
  const totalFirms = Number(firmStats?.total_firms || 0);
  const totalEmployees = Number(firmStats?.total_employees || 0);
  const avgWageOffer = Number(firmStats?.avg_wage_offer || 0);
  const strugglingFirms = Number(firmStats?.struggling_firms || 0);
  const tickMs = metrics?.tickComputeMs || 0;

  const histories = useTickHistory(tick, {
    stress: stressVal,
    tickMs,
    rev,
    out,
    bonds,
    loans,
    firms: totalFirms,
    employees: totalEmployees,
    wageoffer: avgWageOffer,
    wageOffer: avgWageOffer,
    struggling: strugglingFirms,
  }, 250);

  return (
    <div className="app">
      <Rail
        view={activeView}
        onSelect={setActiveView}
        enabled={isInitialized}
        connected={wsConnected}
        sessionId={sessionId}
      />

      <main className="main">
        <TopBar
          view={activeView}
          tick={tick}
          running={isRunning}
          initialized={isInitialized}
          connected={wsConnected}
          onToggleRun={toggleRun}
          onReset={handleReset}
          onToggleTheme={toggleTheme}
          theme={theme}
        />
        <StatusStrip
          sessionId={sessionId}
          metrics={metrics}
          firmStats={firmStats}
          tick={tick}
          population={setupConfig.num_households}
          config={config}
          policyChanges={metrics.policyChanges}
        />

        <div className="view">

            {/* DASHBOARD VIEW */}
            {activeView === 'DASHBOARD' && (
              <Command
                metrics={metrics}
                firmStats={firmStats}
                tick={tick}
                histories={histories}
                policyChanges={metrics.policyChanges}
                llmGov={llmGov}
                latestDecision={latestDecision}
                llmStatusLabel={llmStatusLabel}
              />
            )}

            {/* SUBJECTS VIEW */}
            {activeView === 'SUBJECTS' && (
              <Population
                metrics={metrics}
                tick={tick}
                population={setupConfig.num_households}
                histories={histories}
                subjectIndex={activeSubjectIndex}
                onSelectSubject={setActiveSubjectIndex}
                search={subjectSearch}
                onSearch={setSubjectSearch}
                filter={subjectFilter}
                onFilter={setSubjectFilter}
              />
            )}

            {/* FIRMS VIEW */}
            {activeView === 'FIRMS' && (
              <Markets
                metrics={metrics}
                firmStats={firmStats}
                tick={tick}
                histories={histories}
                firmIndex={activeFirmIndex}
                onSelectFirm={setActiveFirmIndex}
              />
            )}

            {/* FINANCE VIEW */}
            {activeView === 'FINANCE' && (
              <Finance
                metrics={metrics}
                tick={tick}
                histories={histories}
                policyChanges={metrics.policyChanges}
              />
            )}

            {/* GOVERNMENT VIEW */}
            {activeView === 'GOVERNMENT' && (
              <Government
                metrics={metrics}
                tick={tick}
                histories={histories}
                config={config}
                onConfigChange={handleConfigChange}
                enumOptions={enumOptions}
                isAiActive={isPolicyAssistantActive}
                llmGov={llmGov}
                latestDecision={latestDecision}
                llmStatusLabel={llmStatusLabel}
                llmActivityLevel={llmActivityLevel}
                friendlyModelName={friendlyModelName}
              />
            )}

            {/* CONFIG VIEW */}
            {activeView === 'CONFIG' && (
              <Config
                setupConfig={setupConfig}
                onSetupChange={handleSetupChange}
                config={config}
                onConfigChange={handleConfigChange}
                isInitialized={isInitialized}
                isInitializing={isInitializing}
                wsConnected={wsConnected}
                wsEndpoint={wsEndpoint}
                sessionId={sessionId}
                histories={histories}
                onLaunch={handleInitialize}
                onResetDefaults={resetPolicyDefaults}
                onApply={flushConfigUpdates}
                stabilizerAgentOptions={stabilizerAgentOptions}
                enumOptions={enumOptions}
              />
            )}

            {/* LOGS VIEW */}
            {activeView === 'LOGS' && (
              <Logs
                logs={logs}
                tick={tick}
                metrics={metrics}
                selectedLogId={selectedLogId}
                onSelectLog={setSelectedLogId}
                histories={histories}
                typeFilter={logTypeFilter}
                onTypeFilter={setLogTypeFilter}
                severityFilter={logSeverityFilter}
                onSeverityFilter={setLogSeverityFilter}
                search={logSearch}
                onSearch={setLogSearch}
                density={logDensity}
                onDensity={setLogDensity}
                autoScroll={autoScrollLogs}
                onAutoScroll={setAutoScrollLogs}
              />
            )}

            {/* Page wrapper close */}
        </div>
      </main>
    </div>
  );
}
