import { useState, useRef, useEffect } from 'react';
import {
    Send, Sparkles, Scale, BookOpen, AlertTriangle,
    MessageSquare, ShieldAlert, Search, Loader2, FileText, Copy, Check
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './LegalAid.css';

const SUGGESTIONS = [
    { text: "What are the rules for filing an Anticipatory Bail under Section 438 CrPC?", icon: ShieldAlert },
    { text: "My landlord is refusing to return my security deposit. What is my legal recourse?", icon: Scale },
    { text: "How do I secure an ex-parte injunction against illegal demolition?", icon: AlertTriangle },
    { text: "Can an FIR be quashed under Section 482 CrPC if the parties compromise?", icon: BookOpen },
];

const parseAnswer = (rawAnswer) => {
    const sections = {
        directAnswer: '',
        legalBasis: '',
        precedents: '',
        insight: '',
        disclaimer: '',
    };

    const directMatch = rawAnswer.match(/DIRECT ANSWER:\s*([\s\S]*?)(?=LEGAL BASIS:|$)/i);
    const legalMatch = rawAnswer.match(/LEGAL BASIS:\s*([\s\S]*?)(?=BINDING PRECEDENTS:|$)/i);
    const precedentsMatch = rawAnswer.match(/BINDING PRECEDENTS:\s*([\s\S]*?)(?=ACTIONABLE INSIGHT:|$)/i);
    const insightMatch = rawAnswer.match(/ACTIONABLE INSIGHT:\s*([\s\S]*?)(?=DISCLAIMER:|$)/i);
    const disclaimerMatch = rawAnswer.match(/DISCLAIMER:\s*([\s\S]*?)$/i);

    if (directMatch) sections.directAnswer = directMatch[1].trim();
    if (legalMatch) sections.legalBasis = legalMatch[1].trim();
    if (precedentsMatch) sections.precedents = precedentsMatch[1].trim();
    if (insightMatch) sections.insight = insightMatch[1].trim();
    if (disclaimerMatch) sections.disclaimer = disclaimerMatch[1].trim();

    if (!sections.directAnswer) sections.directAnswer = rawAnswer;

    return sections;
};

const LegalAid = () => {
    const { getAuthHeaders } = useAuth();

    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isThinking, setIsThinking] = useState(false);
    const [loadingStage, setLoadingStage] = useState(0);

    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isThinking]);

    const handleSend = async (queryText) => {
        const text = queryText || inputValue;
        if (!text.trim() || isThinking) return;

        const userMsg = { id: 'msg_' + Date.now(), type: 'user', text };
        setMessages(prev => [...prev, userMsg]);
        setInputValue('');
        setIsThinking(true);
        setLoadingStage(0);

        const stageTimer1 = setTimeout(() => setLoadingStage(1), 1200);
        const stageTimer2 = setTimeout(() => setLoadingStage(2), 2500);

        try {
            const response = await fetch('/api/legal-aid/ask', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ question: text, n_results: 3 }),
            });

            clearTimeout(stageTimer1);
            clearTimeout(stageTimer2);

            if (!response.ok) {
                let msg = 'Request failed';
                try { const e = await response.json(); msg = e.detail || msg; } catch { msg = `Server error (${response.status})`; }
                throw new Error(msg);
            }

            const data = await response.json();
            const parsed = parseAnswer(data.answer);

            const aiMsg = {
                id: 'ai_' + Date.now(),
                type: 'structured_ai',
                raw: data.answer,
                data: {
                    answer: parsed.directAnswer,
                    legal_basis: parsed.legalBasis || 'Refer to relevant Indian statutes and case law.',
                    references: parsed.precedents ? parsed.precedents.split('\n').filter(Boolean) : [],
                    insight: parsed.insight || '',
                    disclaimer: parsed.disclaimer,
                    tags: data.sources?.map(s => s.category).filter((v, i, a) => a.indexOf(v) === i).slice(0, 3) || [],
                    sources: data.sources || [],
                }
            };

            setMessages(prev => [...prev, aiMsg]);
        } catch (err) {
            const errorMsg = {
                id: 'err_' + Date.now(),
                type: 'error',
                text: err.message,
            };
            setMessages(prev => [...prev, errorMsg]);
        } finally {
            setIsThinking(false);
        }
    };

    return (
        <div className="intelligence-workspace-layout">
            <aside className="intelligence-sidebar">
                <div className="sidebar-header-workspace"><h3>Legal Intelligence</h3></div>
                <div className="sidebar-category-group">
                    <div className="template-item active">
                        <MessageSquare size={18} className="template-icon" />
                        <div><h4>AI Legal Assistant</h4></div>
                    </div>
                </div>
            </aside>

            <main className="intelligence-feed-area">
                <div className="feed-app-header">
                    <div className="header-titles">
                        <h2>Legal Aid Intelligence</h2>
                        <p>AI-powered legal guidance grounded in IPC, CrPC, CPC, and the Constitution of India.</p>
                    </div>
                </div>

                <div className="disclaimer-soft-box">
                    <ShieldAlert size={20} className="disclaimer-icon" />
                    <p><strong>Notice:</strong> This AI provides legal information for reference only. It does not constitute attorney-client advice.</p>
                </div>

                <div className="intelligence-messages-river">
                    {messages.length === 0 ? (
                        <div className="empty-sandbox-state animate-fade-in">
                            <Sparkles size={48} className="text-primary mb-4 opacity-50 mx-auto" />
                            <h2>How can NyayaSetu help you today?</h2>
                            <div className="suggestion-chips-grid">
                                {SUGGESTIONS.map((sug, idx) => (
                                    <button key={idx} className="suggestion-chip" onClick={() => handleSend(sug.text)}>
                                        <sug.icon size={18} className="chip-icon" />
                                        <span>{sug.text}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        messages.map((msg) => (
                            <div key={msg.id} className={`message-wrapper ${msg.type === 'user' ? 'user-wrapper' : 'ai-wrapper'}`}>
                                {msg.type === 'user' && (
                                    <div className="user-query-bubble"><p>{msg.text}</p></div>
                                )}

                                {msg.type === 'error' && (
                                    <div className="user-query-bubble" style={{ background: '#fee2e2', color: '#991b1b' }}>
                                        <p>Error: {msg.text}. Please ensure the backend is running.</p>
                                    </div>
                                )}

                                {msg.type === 'structured_ai' && (
                                    <div className="ai-intelligence-card animate-fade-in">
                                        <div className="card-top-accent"></div>
                                        <div className="ai-card-content">

                                            <div className="intelligence-block">
                                                <h4 className="flex items-center gap-2 font-bold mb-2 text-primary">
                                                    <FileText size={16} /> Direct Answer
                                                </h4>
                                                <p>{msg.data.answer}</p>
                                            </div>

                                            {msg.data.legal_basis && (
                                                <div className="intelligence-block border-l-4 border-gray-400 pl-4 py-1">
                                                    <h4 className="flex items-center gap-2 font-bold mb-2 text-gray-800">
                                                        <Scale size={16} /> Legal Basis
                                                    </h4>
                                                    <p className="text-gray-600 text-sm leading-relaxed">{msg.data.legal_basis}</p>
                                                </div>
                                            )}

                                            {msg.data.references.length > 0 && (
                                                <div className="intelligence-block blue-tint">
                                                    <h4 className="flex items-center gap-2 font-bold mb-2 text-blue-900">
                                                        <BookOpen size={16} /> Precedents Cited
                                                    </h4>
                                                    <ul className="list-disc pl-5 text-sm text-blue-800 space-y-1">
                                                        {msg.data.references.map((ref, i) => (
                                                            <li key={i}>{ref}</li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {msg.data.insight && (
                                                <div className="intelligence-block bg-gray-900 text-white rounded-lg p-4">
                                                    <h4 className="flex items-center gap-2 font-bold mb-2 text-blue-300 uppercase tracking-wider text-xs">
                                                        <AlertTriangle size={14} /> Actionable Insight
                                                    </h4>
                                                    <p className="text-sm">{msg.data.insight}</p>
                                                </div>
                                            )}

                                        </div>

                                        <div className="ai-card-footer">
                                            <div className="card-tags-group">
                                                {msg.data.tags.map((tag, i) => (
                                                    <span key={i} className="legal-tag">{tag}</span>
                                                ))}
                                            </div>
                                            <div className="card-quick-actions">
                                                <button
                                                    className="quick-action-btn"
                                                    onClick={() => navigator.clipboard.writeText(msg.raw)}
                                                >
                                                    <Copy size={14} /> Copy
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))
                    )}

                    {isThinking && (
                        <div className="message-wrapper ai-wrapper">
                            <div className="ai-spinner-card animate-fade-in">
                                <Loader2 size={24} className="spin text-primary mr-3" />
                                <span className="spinner-text">
                                    {loadingStage === 0 && "Parsing legal query..."}
                                    {loadingStage === 1 && "Cross-referencing statutory databases (CrPC / IPC)..."}
                                    {loadingStage === 2 && "Compiling precedents and actionable insights..."}
                                </span>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                <div className="huge-input-assembly">
                    <div className="search-bar-wrapper">
                        <Search size={22} className="input-search-icon" />
                        <input
                            type="text"
                            className="massive-legal-input"
                            placeholder="Ask about bail, contracts, property rights, consumer protection, labour law..."
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) handleSend(); }}
                        />
                        <button
                            className={`massive-send-btn ${inputValue.trim() ? 'active' : ''}`}
                            onClick={() => handleSend()}
                            disabled={!inputValue.trim() || isThinking}
                        >
                            <Send size={18} />
                        </button>
                    </div>
                    <div className="input-footnote">
                        <ShieldAlert size={12} /> Obfuscate confidential names or PII before querying.
                    </div>
                </div>
            </main>
        </div>
    );
};

export default LegalAid;
