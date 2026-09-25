import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft, BookOpen, Code, Zap, FolderOpen, Clock, Loader2, AlertCircle, FileCode, CheckCircle2, Send, MessageSquare, Terminal, GitPullRequest, Copy, CheckSquare, PartyPopper } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const CopyButton = ({ text }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button className="copy-btn-sm" onClick={handleCopy} title="Copy to clipboard">
      {copied ? <CheckCircle2 size={14} color="#10b981" /> : <Copy size={14} />}
    </button>
  );
};

const difficultyConfig = {
  Beginner: { color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)', icon: BookOpen },
  Intermediate: { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.3)', icon: Code },
  Advanced: { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)', icon: Zap },
};

export default function Workspace({ opportunity, repoUrl, onBack }) {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Chat State
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);

  // Progress State
  const [checklist, setChecklist] = useState({
    review: false,
    implement: false,
    test: false,
    commit: false,
    pr: false
  });

  const handleCheck = (key) => {
    setChecklist(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const isComplete = Object.values(checklist).every(Boolean);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, isSending]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isSending) return;
    
    const userMessage = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsSending(true);
    
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo_url: repoUrl,
          opportunity,
          plan: plan,
          messages: chatMessages,
          new_message: userMessage
        })
      });
      
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Chat failed');
      
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      console.error(err);
      setChatMessages(prev => [...prev, { role: 'assistant', content: `**Error:** ${err.message}` }]);
    } finally {
      setIsSending(false);
    }
  };

      useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setPlan(null);
    setChecklist({ review: false, implement: false, test: false, commit: false, pr: false });

    const fetchPlan = async () => {
      try {
        const response = await fetch('/api/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repo_url: repoUrl, opportunity }),
        });

        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.detail || 'Failed to generate implementation plan.');
        }

        if (isMounted) {
          setPlan(data.plan);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          console.error(err);
          setError(err.message || 'An error occurred while generating the plan.');
          setLoading(false);
        }
      }
    };

    fetchPlan();

    return () => {
      isMounted = false;
    };
  }, [opportunity, repoUrl]);

  const config = difficultyConfig[opportunity.difficulty] || difficultyConfig.Beginner;
  const DiffIcon = config.icon;

  return (
    <div className="workspace-container">
      {/* Back button */}
      <button className="workspace-back-btn" onClick={onBack}>
        <ArrowLeft size={16} />
        Back to opportunities
      </button>

      {/* Header */}
      <div className="workspace-header">
        <h2 className="workspace-title">{opportunity.title}</h2>
        <div className="workspace-meta">
          <span
            className="opp-difficulty-badge"
            style={{ color: config.color, background: config.bg, borderColor: config.border }}
          >
            <DiffIcon size={12} />
            {opportunity.difficulty}
          </span>
          <span className="opp-category-badge">{opportunity.category}</span>
          {opportunity.estimated_effort && (
            <span className="workspace-effort">
              <Clock size={14} />
              {opportunity.estimated_effort}
            </span>
          )}
        </div>
      </div>

      {/* Progress Checklist */}
      <div className="workspace-section">
        <h3 className="workspace-section-title">
          <CheckSquare size={16} />
          Your Progress
        </h3>
        
        {isComplete && (
          <div className="celebration-banner animation-fade-in">
            <PartyPopper size={32} color="#10b981" />
            <div className="celebration-content">
              <h4>Contribution Complete!</h4>
              <p>You've successfully completed the end-to-end flow for <strong>{opportunity.title}</strong>.</p>
              <div className="celebration-actions">
                <button className="submit-btn" style={{ marginTop: '0.5rem', fontSize: '0.9rem', padding: '0.6rem 1.25rem' }} onClick={onBack}>
                  Pick another opportunity
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="checklist-container">
          <label className={`checklist-item ${checklist.review ? 'checked' : ''}`}>
            <input type="checkbox" checked={checklist.review} onChange={() => handleCheck('review')} />
            <span className="checklist-text">Review Opportunity & Plan</span>
          </label>
          <label className={`checklist-item ${checklist.implement ? 'checked' : ''}`}>
            <input type="checkbox" checked={checklist.implement} onChange={() => handleCheck('implement')} />
            <span className="checklist-text">Implement the Changes</span>
          </label>
          <label className={`checklist-item ${checklist.test ? 'checked' : ''}`}>
            <input type="checkbox" checked={checklist.test} onChange={() => handleCheck('test')} />
            <span className="checklist-text">Run Tests</span>
          </label>
          <label className={`checklist-item ${checklist.commit ? 'checked' : ''}`}>
            <input type="checkbox" checked={checklist.commit} onChange={() => handleCheck('commit')} />
            <span className="checklist-text">Commit & Push</span>
          </label>
          <label className={`checklist-item ${checklist.pr ? 'checked' : ''}`}>
            <input type="checkbox" checked={checklist.pr} onChange={() => handleCheck('pr')} />
            <span className="checklist-text">Create Pull Request</span>
          </label>
        </div>
        
        <div className="progress-bar-container">
          <div className="progress-bar-fill" style={{ width: `${(Object.values(checklist).filter(Boolean).length / 5) * 100}%` }}></div>
        </div>
      </div>

      {/* Description */}
      <div className="workspace-section">
        <h3 className="workspace-section-title">Description</h3>
        <p className="workspace-section-text">{opportunity.description}</p>
      </div>

      {/* Learning Path */}
      {opportunity.learning_path && (
        <div className="workspace-section">
          <h3 className="workspace-section-title">
            <BookOpen size={16} />
            Learning Path
          </h3>
          <div className="workspace-learning-steps">
            {opportunity.learning_path.split('\n').map((step, i) => (
              <div key={i} className="workspace-step">
                <span className="workspace-step-num">{i + 1}</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Relevant Files */}
      {opportunity.relevant_files && opportunity.relevant_files.length > 0 && (
        <div className="workspace-section">
          <h3 className="workspace-section-title">
            <FolderOpen size={16} />
            Context Files
          </h3>
          <ul className="workspace-files-list">
            {opportunity.relevant_files.map((file, i) => (
              <li key={i} className="workspace-file-item">
                <code>{file}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Dynamic Plan Section */}
      <div className="workspace-plan-section">
        <h2 className="workspace-title" style={{ fontSize: '1.75rem', marginTop: '2rem' }}>Implementation Plan</h2>
        
        {loading && (
          <div className="loading-box" style={{ marginTop: '1rem' }}>
            <div className="loading-header">
              <Loader2 className="spinner" size={18} />
              <span>Generating actionable implementation plan...</span>
            </div>
            <p className="workspace-section-text" style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)' }}>
              Our AI is analyzing the repository context to provide concrete, step-by-step instructions.
            </p>
          </div>
        )}

        {error && (
          <div className="error-banner">
            <AlertCircle size={20} />
            <div>
              <strong>Plan Generation Failed</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {plan && !loading && (
          <div className="plan-content animation-fade-in">
            <div className="workspace-section">
              <h3 className="workspace-section-title">Summary</h3>
              <p className="workspace-section-text">{plan.summary}</p>
              {plan.estimated_time && (
                <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-primary)' }}>
                  <Clock size={16} />
                  <strong>Estimated time:</strong> {plan.estimated_time}
                </div>
              )}
            </div>

            {plan.relevant_files && plan.relevant_files.length > 0 && (
              <div className="workspace-section">
                <h3 className="workspace-section-title">
                  <FileCode size={16} />
                  Target Files
                </h3>
                <ul className="plan-files-list">
                  {plan.relevant_files.map((file, idx) => (
                    <li key={idx} className="plan-file-item">
                      <code>{file.path}</code>
                      <p className="plan-file-reason">{file.reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="workspace-section">
              <h3 className="workspace-section-title">
                <CheckCircle2 size={16} />
                Implementation Steps
              </h3>
              <div className="plan-steps-container">
                {plan.steps && plan.steps.map((step) => (
                  <div key={step.step_number} className="plan-step-card">
                    <div className="plan-step-header">
                      <span className="plan-step-number">{step.step_number}</span>
                      <h4 className="plan-step-title">{step.title}</h4>
                    </div>
                    <p className="plan-step-desc">{step.description}</p>
                    
                    {step.files_to_modify && step.files_to_modify.length > 0 && (
                      <div className="plan-step-files">
                        <strong>Modifies:</strong>
                        <div className="plan-step-file-tags">
                          {step.files_to_modify.map((f, i) => <code key={i}>{f}</code>)}
                        </div>
                      </div>
                    )}
                    
                    <div className="plan-step-acceptance">
                      <strong>Acceptance:</strong> {step.acceptance_criteria}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {plan.potential_pitfalls && plan.potential_pitfalls.length > 0 && (
              <div className="workspace-section" style={{ background: 'rgba(239, 68, 68, 0.05)', borderColor: 'rgba(239, 68, 68, 0.2)' }}>
                <h3 className="workspace-section-title" style={{ color: '#ef4444' }}>
                  <AlertCircle size={16} />
                  Potential Pitfalls
                </h3>
                <ul className="plan-pitfalls-list" style={{ color: 'var(--color-text-main)', paddingLeft: '1.5rem' }}>
                  {plan.potential_pitfalls.map((pitfall, idx) => (
                    <li key={idx} style={{ marginBottom: '0.5rem' }}>{pitfall}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Testing Guidance */}
            {plan.testing && (
              <div className="workspace-section">
                <h3 className="workspace-section-title">
                  <Terminal size={16} />
                  Testing Guidance
                </h3>
                <div className="guidance-block">
                  <p><strong>Framework:</strong> {plan.testing.detected_framework}</p>
                  
                  <div className="guidance-code-block">
                    <div className="guidance-code-header">
                      <span>Commands</span>
                      <CopyButton text={plan.testing.suggested_commands.join('\n')} />
                    </div>
                    <pre><code>{plan.testing.suggested_commands.join('\n')}</code></pre>
                  </div>
                  
                  <p><strong>Verification:</strong> {plan.testing.how_to_verify}</p>
                  
                  {plan.testing.common_failures && plan.testing.common_failures.length > 0 && (
                    <div className="guidance-tips">
                      <strong>Common Failures:</strong>
                      <ul style={{ paddingLeft: '1.5rem', marginTop: '0.5rem' }}>
                        {plan.testing.common_failures.map((tip, idx) => <li key={idx}>{tip}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Git & PR Guidance */}
            {plan.git_pr && (
              <div className="workspace-section">
                <h3 className="workspace-section-title">
                  <GitPullRequest size={16} />
                  Commit, Push & PR Guidance
                </h3>
                
                <div className="guidance-block">
                  <p style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <strong>Branch:</strong> <code>{plan.git_pr.suggested_branch_name}</code> 
                    <CopyButton text={plan.git_pr.suggested_branch_name} />
                  </p>
                  
                  <div className="guidance-code-block">
                    <div className="guidance-code-header">
                      <span>Commit Message</span>
                      <CopyButton text={plan.git_pr.commit_message} />
                    </div>
                    <pre><code>{plan.git_pr.commit_message}</code></pre>
                  </div>
                  
                  <p style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <strong>PR Title:</strong> {plan.git_pr.pr_title} 
                    <CopyButton text={plan.git_pr.pr_title} />
                  </p>
                  
                  <div className="guidance-code-block">
                    <div className="guidance-code-header">
                      <span>PR Body (Markdown)</span>
                      <CopyButton text={plan.git_pr.pr_body} />
                    </div>
                    <pre><code>{plan.git_pr.pr_body}</code></pre>
                  </div>

                  <div className="guidance-code-block">
                    <div className="guidance-code-header">
                      <span>Git Commands</span>
                      <CopyButton text={plan.git_pr.commands.join('\n')} />
                    </div>
                    <pre><code>{plan.git_pr.commands.join('\n')}</code></pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Interactive Chat Panel */}
      <div className="workspace-chat-section">
        <h3 className="workspace-section-title">
          <MessageSquare size={16} />
          Mentor Chat
        </h3>
        <p className="workspace-section-text" style={{ fontSize: '0.9rem', marginBottom: '1rem', color: 'var(--color-text-muted)' }}>
          Have questions about this opportunity or the implementation plan? Ask your AI mentor!
        </p>

        <div className="chat-container">
          <div className="chat-messages">
            {chatMessages.length === 0 && (
              <div className="chat-empty">
                Send a message to start chatting with your mentor.
              </div>
            )}
            {chatMessages.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.role}`}>
                <div className="chat-message-bubble markdown-body-chat">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {isSending && (
              <div className="chat-message assistant">
                <div className="chat-message-bubble loading">
                  <Loader2 className="spinner" size={16} />
                  <span>Thinking...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="chat-input-form" onSubmit={handleSendMessage}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask a question..."
              disabled={isSending}
              className="chat-input"
            />
            <button type="submit" disabled={!chatInput.trim() || isSending} className="chat-send-btn">
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
