import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Bot, 
  Github, 
  Sparkles, 
  FileText, 
  MapPin, 
  Copy, 
  Download, 
  Check, 
  AlertCircle, 
  Loader2, 
  ArrowRight,
  RefreshCw,
  Sun,
  Moon,
  LayoutGrid
} from 'lucide-react';
import OpportunityCard from './OpportunityCard';
import Workspace from './Workspace';

export default function App() {
  const [repoUrl, setRepoUrl] = useState('https://github.com/google/adk-python');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('opportunities'); // 'project_analysis' | 'contribution_roadmap' | 'opportunities'
  const [activeOpportunity, setActiveOpportunity] = useState(null);
  const [copied, setCopied] = useState(false);
  
  // Theme state: defaults to dark
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('repobuddy_theme') || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('repobuddy_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const presets = [
    { label: 'google/adk-python', url: 'https://github.com/google/adk-python' },
    { label: 'pallets/flask', url: 'https://github.com/pallets/flask' },
    { label: 'fastapi/fastapi', url: 'https://github.com/fastapi/fastapi' }
  ];

  const handleAnalyze = async (e) => {
    if (e) e.preventDefault();
    if (!repoUrl.trim()) return;

    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });

      const resData = await response.json();

      if (!response.ok) {
        throw new Error(resData.detail || 'Analysis request failed.');
      }

      setData(resData);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to analyze repository. Please ensure the backend server (api.py) is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!data) return;
    const content = activeTab === 'project_analysis' ? data.project_analysis : data.contribution_roadmap;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!data) return;
    const isPA = activeTab === 'project_analysis';
    const content = isPA ? data.project_analysis : data.contribution_roadmap;
    const filename = isPA ? 'ProjectAnalysis.md' : 'ContributionRoadmap.md';
    
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const currentMarkdown = data 
    ? (activeTab === 'project_analysis' ? data.project_analysis : data.contribution_roadmap)
    : '';

  return (
    <div className="app-root">
      {/* App Header */}
      <header className="app-header">
        <div className="header-container">
          <a href="#" className="logo-brand">
            <div className="logo-icon">
              <Bot size={24} />
            </div>
            <span className="logo-text">RepoBuddy</span>
            <span className="logo-tag">AI Mentor</span>
          </a>

          <div className="header-right">
            {/* Theme Toggle Button */}
            <button 
              className="theme-toggle-btn" 
              onClick={toggleTheme}
              title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
            </button>

            {data && (
              <button className="action-btn" onClick={() => { setData(null); setError(null); }}>
                <RefreshCw size={14} /> Analyze Another Repo
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="main-content">
        {/* Hero Section */}
        <div className="hero-section">
          <h1 className="hero-title">
            Your AI Open Source <span>Mentor</span>
          </h1>
          <p className="hero-subtitle">
            Enter any public GitHub repository link below to generate structured project architecture insights and a personalized contribution roadmap.
          </p>

          {/* URL Input Form */}
          <div className="input-card">
            <form onSubmit={handleAnalyze} className="input-form">
              <div className="input-group">
                <Github className="input-icon" size={20} />
                <input
                  type="text"
                  className="url-input"
                  placeholder="https://github.com/owner/repository"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  disabled={loading}
                />
              </div>
              <button type="submit" className="submit-btn" disabled={loading || !repoUrl.trim()}>
                {loading ? (
                  <>
                    <Loader2 className="spinner" size={18} />
                    Analyzing...
                  </>
                ) : (
                  <>
                    Analyze <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>

            {/* Quick Presets */}
            <div className="presets-row">
              <span>Try example:</span>
              {presets.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  className="preset-pill"
                  onClick={() => setRepoUrl(p.url)}
                  disabled={loading}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Progress Status when Loading */}
            {loading && (
              <div className="loading-box">
                <div className="loading-header">
                  <Sparkles className="spinner" size={18} />
                  <span>Agent Mentorship Flow Active...</span>
                </div>
                <div className="steps-list">
                  <div className="step-item active">
                    <span className="step-dot"></span>
                    <span>1. Repository Exploration & Structure Inspection</span>
                  </div>
                  <div className="step-item active">
                    <span className="step-dot"></span>
                    <span>2. GitHub Metrics Intelligence & Issue Triage</span>
                  </div>
                  <div className="step-item active">
                    <span className="step-dot"></span>
                    <span>3. Architectural Reasoning & Framework Identification</span>
                  </div>
                  <div className="step-item active">
                    <span className="step-dot"></span>
                    <span>4. Discovering Scored Contribution Opportunities</span>
                  </div>
                  <div className="step-item active">
                    <span className="step-dot"></span>
                    <span>5. Synthesizing Markdown Deliverable Reports</span>
                  </div>
                </div>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="error-banner">
                <AlertCircle size={20} />
                <div>
                  <strong>Analysis Error</strong>
                  <p>{error}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Results Viewer */}
        {data && (
          <div className="results-container">
            {/* Tab Navigation Header */}
            <div className="tab-header">
              <div className="tab-buttons">
                <button
                  className={`tab-btn ${activeTab === 'opportunities' ? 'active' : ''}`}
                  onClick={() => { setActiveTab('opportunities'); setActiveOpportunity(null); }}
                >
                  <LayoutGrid size={18} />
                  Opportunities
                </button>
                <button
                  className={`tab-btn ${activeTab === 'project_analysis' ? 'active' : ''}`}
                  onClick={() => { setActiveTab('project_analysis'); setActiveOpportunity(null); }}
                >
                  <FileText size={18} />
                  Project Analysis
                </button>

                <button
                  className={`tab-btn ${activeTab === 'contribution_roadmap' ? 'active' : ''}`}
                  onClick={() => { setActiveTab('contribution_roadmap'); setActiveOpportunity(null); }}
                >
                  <MapPin size={18} />
                  Roadmap (MD)
                </button>
              </div>

              <div className="tab-actions">
                <button className="action-btn" onClick={handleCopy}>
                  {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                  {copied ? 'Copied!' : 'Copy Markdown'}
                </button>
                <button className="action-btn" onClick={handleDownload}>
                  <Download size={14} />
                  Download .md
                </button>
              </div>
            </div>

            {/* Main Content Area */}
            {activeTab === 'opportunities' ? (
              <div className="opportunities-area">
                {activeOpportunity ? (
                  <Workspace 
                    opportunity={activeOpportunity} 
                    repoUrl={repoUrl}
                    onBack={() => setActiveOpportunity(null)} 
                  />
                ) : (
                  <div className="opportunities-grid">
                    {data.opportunities && data.opportunities.length > 0 ? (
                      data.opportunities.map(opp => (
                        <OpportunityCard 
                          key={opp.id} 
                          opportunity={opp} 
                          onClick={() => setActiveOpportunity(opp)} 
                        />
                      ))
                    ) : (
                      <div className="no-opportunities">
                        <AlertCircle size={24} />
                        <p>No structured opportunities found in the analysis.</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {currentMarkdown}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
