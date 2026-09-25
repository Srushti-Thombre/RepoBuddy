import React from 'react';
import { ArrowRight, Code, BookOpen, Zap } from 'lucide-react';

const difficultyConfig = {
  Beginner: { color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)', icon: BookOpen },
  Intermediate: { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.3)', icon: Code },
  Advanced: { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)', icon: Zap },
};

export default function OpportunityCard({ opportunity, onClick }) {
  const config = difficultyConfig[opportunity.difficulty] || difficultyConfig.Beginner;
  const DiffIcon = config.icon;

  return (
    <button className="opp-card" onClick={onClick}>
      <div className="opp-card-top">
        <span
          className="opp-difficulty-badge"
          style={{ color: config.color, background: config.bg, borderColor: config.border }}
        >
          <DiffIcon size={12} />
          {opportunity.difficulty}
        </span>
        <span className="opp-category-badge">{opportunity.category}</span>
      </div>

      <h3 className="opp-card-title">{opportunity.title}</h3>

      <p className="opp-card-desc">
        {opportunity.description.length > 150
          ? opportunity.description.slice(0, 150) + '...'
          : opportunity.description}
      </p>

      <div className="opp-card-footer">
        {opportunity.estimated_effort && (
          <span className="opp-effort">{opportunity.estimated_effort}</span>
        )}
        <span className="opp-view-link">
          View details <ArrowRight size={14} />
        </span>
      </div>
    </button>
  );
}
