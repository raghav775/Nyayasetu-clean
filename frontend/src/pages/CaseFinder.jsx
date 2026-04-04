import { useState } from 'react';
import {
    Search, BookOpen, Gavel, Sparkles, TrendingUp, AlertCircle,
    ChevronDown, ExternalLink, Tag
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './CaseFinder.css';

const SUGGESTIONS = [
    "Breach of specific performance",
    "Anticipatory bail under Section 438 CrPC",
    "Section 138 Negotiable Instruments Act cheque dishonour",
    "Wrongful termination of employment",
    "Dowry harassment IPC 498A",
];

const CaseFinder = () => {
    const { getAuthHeaders } = useAuth();

    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [hasSearched, setHasSearched] = useState(false);
    const [error, setError] = useState('');

    const [aiAnswer, setAiAnswer] = useState('');
    const [localSources, setLocalSources] = useState([]);
    const [liveCases, setLiveCases] = useState([]);
    const [judgementKeywords, setJudgementKeywords] = useState([]);

    const [activeCourt, setActiveCourt] = useState('All Courts');
    const [activeYear, setActiveYear] = useState('All Years');

    const handleSearch = async (e) => {
        if (e) e.preventDefault();
        await handleSearchWithQuery(searchQuery);
    };

    const triggerSearch = (query) => {
        setSearchQuery(query);
        setTimeout(() => {
            handleSearchWithQuery(query);
        }, 0);
    };

    const handleSearchWithQuery = async (query) => {
        if (!query.trim()) return;

        setIsSearching(true);
        setHasSearched(false);
        setError('');
        setAiAnswer('');
        setLocalSources([]);
        setLiveCases([]);
        setJudgementKeywords([]);

        try {
            const response = await fetch('/api/cases/search', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ query, n_results: 5 }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Search failed');
            }

            const data = await response.json();
            setAiAnswer(data.answer);
            setLocalSources(data.sources || []);
            setLiveCases(data.live_cases || []);

            // Extract all unique keywords from all live case judgements
            const allKeywords = [
                ...new Set(
                    (data.live_cases || []).flatMap(c => c.keywords || [])
                )
            ];
            setJudgementKeywords(allKeywords);
            setHasSearched(true);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsSearching(false);
        }
    };

    return (
        <div className="research-layout">
            <aside className="filters-sidebar">
                <div className="filter-header">
                    <h3>Refine Search</h3>
                    <button className="clear-btn" onClick={() => { setActiveCourt('All Courts'); setActiveYear('All Years'); }}>
                        Clear All
                    </button>
                </div>

                <div className="filter-group">
                    <label>Jurisdiction</label>
                    <div className="custom-select">
                        <select value={activeCourt} onChange={e => setActiveCourt(e.target.value)}>
                            <option>All Courts</option>
                            <option>Supreme Court of India</option>
                            <option>Delhi High Court</option>
                            <option>Bombay High Court</option>
                            <option>Madras High Court</option>
                        </select>
                        <ChevronDown size={14} className="select-icon" />
                    </div>
                </div>

                <div className="filter-group">
                    <label>Timeline</label>
                    <div className="custom-select">
                        <select value={activeYear} onChange={e => setActiveYear(e.target.value)}>
                            <option>All Years</option>
                            <option>2023 - Present</option>
                            <option>2010 - 2022</option>
                            <option>Pre-2010</option>
                        </select>
                        <ChevronDown size={14} className="select-icon" />
                    </div>
                </div>

                <div className="filter-group">
                    <label>Area of Law</label>
                    <div className="checkbox-list">
                        <label className="checkbox-item"><input type="checkbox" defaultChecked /> <span>Constitutional</span></label>
                        <label className="checkbox-item"><input type="checkbox" defaultChecked /> <span>Criminal</span></label>
                        <label className="checkbox-item"><input type="checkbox" /> <span>Corporate</span></label>
                        <label className="checkbox-item"><input type="checkbox" /> <span>Family</span></label>
                    </div>
                </div>

                {/* Keywords from Judgements Panel */}
                {judgementKeywords.length > 0 && (
                    <div className="filter-group" style={{ marginTop: '1.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
                            <Tag size={13} style={{ color: 'var(--primary, #2d7dd2)' }} />
                            <label style={{ margin: 0 }}>Keywords from Judgements</label>
                        </div>
                        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted, #8BA5BE)', marginBottom: '0.75rem', lineHeight: '1.5' }}>
                            Click any keyword to search cases containing it
                        </p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                            {judgementKeywords.slice(0, 20).map((kw, i) => (
                                <span
                                    key={i}
                                    onClick={() => triggerSearch(kw)}
                                    style={{
                                        cursor: 'pointer',
                                        fontSize: '0.68rem',
                                        padding: '0.2rem 0.55rem',
                                        background: 'rgba(45,125,210,0.12)',
                                        color: '#93c5fd',
                                        borderRadius: '4px',
                                        border: '1px solid rgba(45,125,210,0.3)',
                                        transition: 'all 0.15s',
                                        userSelect: 'none',
                                    }}
                                    onMouseEnter={e => e.target.style.background = 'rgba(45,125,210,0.25)'}
                                    onMouseLeave={e => e.target.style.background = 'rgba(45,125,210,0.12)'}
                                    title={`Search: "${kw}"`}
                                >
                                    {kw}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </aside>

            <main className="results-feed">
                <div className="search-header-panel">
                    <form className="advanced-search-bar" onSubmit={handleSearch}>
                        <div className="search-input-area">
                            <Search size={18} className="search-icon text-secondary" />
                            <input
                                type="text"
                                placeholder="Describe the legal issue or cite a case..."
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                            />
                        </div>
                        <button type="submit" className="unified-search-btn">
                            Analyze
                        </button>
                    </form>

                    {!hasSearched && !isSearching && (
                        <div className="trending-searches">
                            <span className="trending-label"><TrendingUp size={14} /> Trending:</span>
                            {SUGGESTIONS.map((s, i) => (
                                <span key={i} className="trending-tag" onClick={() => triggerSearch(s)}>{s}</span>
                            ))}
                        </div>
                    )}
                </div>

                <div className="feed-content">
                    {isSearching && (
                        <div className="skeleton-container">
                            <div className="skeleton-summary">
                                <div className="skeleton-box title-skel mb-2"></div>
                                <div className="skeleton-box line-skel w-80 mb-1"></div>
                                <div className="skeleton-box line-skel w-60"></div>
                            </div>
                            {[1, 2, 3].map(i => (
                                <div key={i} className="skeleton-card">
                                    <div className="skeleton-box title-skel mb-3 w-70"></div>
                                    <div className="skeleton-box line-skel mb-2 w-90"></div>
                                    <div className="skeleton-box line-skel w-80"></div>
                                </div>
                            ))}
                        </div>
                    )}

                    {error && (
                        <div className="error-banner" style={{ padding: '1rem', background: '#fee2e2', borderRadius: '8px', color: '#991b1b', margin: '1rem' }}>
                            <AlertCircle size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
                            {error}
                        </div>
                    )}

                    {hasSearched && !isSearching && (
                        <div className="results-display animate-fade-in">
                            <div className="ai-summary-banner glass-panel">
                                <div className="ai-banner-header">
                                    <Sparkles size={18} className="text-primary glow-icon" />
                                    <h4>AI Research Synthesis</h4>
                                </div>
                                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7' }}>{aiAnswer}</p>
                            </div>

                            {liveCases.length > 0 && (
                                <>
                                    <p className="results-count">
                                        {liveCases.length} live case{liveCases.length !== 1 ? 's' : ''} from Indian Kanoon for &quot;{searchQuery}&quot;
                                    </p>
                                    <div className="case-list">
                                        {liveCases.map((c, i) => (
                                            <div key={i} className="case-card glass-panel">
                                                <div className="case-card-header">
                                                    <h3>{c.title}</h3>
                                                    <a
                                                        href={c.link}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="case-citation"
                                                        onClick={e => e.stopPropagation()}
                                                    >
                                                        <ExternalLink size={14} /> View on Indian Kanoon
                                                    </a>
                                                </div>
                                                <div className="case-meta">
                                                    <span className="meta-tag"><Gavel size={14} /> {c.source}</span>
                                                </div>
                                                <div className="case-ai-snippet">
                                                    <div className="snippet-marker"></div>
                                                    <p>{c.snippet}</p>
                                                </div>
                                                {/* Keywords from this specific judgement */}
                                                {c.keywords && c.keywords.length > 0 && (
                                                    <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.35rem', alignItems: 'center' }}>
                                                        <Tag size={11} style={{ color: '#6b7280' }} />
                                                        {c.keywords.map((kw, ki) => (
                                                            <span
                                                                key={ki}
                                                                onClick={() => triggerSearch(kw)}
                                                                style={{
                                                                    cursor: 'pointer',
                                                                    fontSize: '0.65rem',
                                                                    padding: '0.15rem 0.5rem',
                                                                    background: 'rgba(45,125,210,0.1)',
                                                                    color: '#93c5fd',
                                                                    borderRadius: '3px',
                                                                    border: '1px solid rgba(45,125,210,0.25)',
                                                                }}
                                                                title={`Search: "${kw}"`}
                                                            >
                                                                {kw}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </>
                            )}

                            {localSources.length > 0 && (
                                <>
                                    <p className="results-count" style={{ marginTop: '1.5rem' }}>
                                        {localSources.length} reference{localSources.length !== 1 ? 's' : ''} from legal database
                                    </p>
                                    <div className="case-list">
                                        {localSources.map((s, i) => (
                                            <div key={i} className="case-card glass-panel">
                                                <div className="case-card-header">
                                                    <h3>{s.filename}</h3>
                                                    <span className="case-citation">Score: {(s.score * 100).toFixed(0)}%</span>
                                                </div>
                                                <div className="case-meta">
                                                    <span className="meta-tag"><BookOpen size={14} /> {s.category}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {!hasSearched && !isSearching && !error && (
                        <div className="empty-search-state animate-fade-in">
                            <BookOpen size={48} className="empty-icon" />
                            <h2>Intelligent Case Finder</h2>
                            <p>Enter a query to search real Indian court judgments from Indian Kanoon. Keywords extracted directly from judgement text appear in the sidebar — click any to drill deeper.</p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};

export default CaseFinder;
